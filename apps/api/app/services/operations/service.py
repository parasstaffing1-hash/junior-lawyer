from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.matter import Matter
from app.models.operations import (
    ChangeSeverity, CourtCaseChange, CourtCaseSnapshot, CourtCaseTracker, CourtChangeType,
    CourtTrackerStatus, NotificationChannel, NotificationStatus, OperationsPreference,
    WorkflowEscalation, WorkflowEvent, WorkflowNotification, WorkflowRun, WorkflowRunStatus,
    WorkflowTask, WorkflowTaskPriority, WorkflowTaskStatus, WorkflowTemplate,
    WorkflowTemplateStatus,
)
from app.models.procedure import DeadlineStatus, Hearing, HearingStatus, MatterDeadline
from app.models.security import MembershipStatus, OrganizationMembership, OrganizationRole, SecurityUser
from app.schemas.operations import (
    CourtSnapshotCreate, CourtTrackerCreate, OperationsPreferenceUpdate, SweepRequest,
    WorkflowTaskCreate, WorkflowTaskUpdate,
)
from app.services.operations.diff import detect_snapshot_changes, stable_snapshot_hash
from app.services.security.context import ActorContext
from app.services.security.permissions import decide_matter_access, visible_matter_ids
from app.models.security import MatterAccessLevel


OPS_ROLES = {
    OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER,
    OrganizationRole.LAWYER, OrganizationRole.JUNIOR, OrganizationRole.PARALEGAL,
}
OPS_MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER, OrganizationRole.LAWYER}
PARTNER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require(actor: ActorContext, roles: set[OrganizationRole]) -> None:
    if actor.role not in roles:
        raise HTTPException(403, "Your role does not permit this court-operations action")


async def _matter(db: AsyncSession, actor: ActorContext, matter_id: UUID, *, required=MatterAccessLevel.VIEW) -> Matter:
    matter = await db.get(Matter, matter_id)
    if not matter or matter.organization_id != actor.organization_id:
        raise HTTPException(404, "Matter not found")
    decision = await decide_matter_access(db, actor, matter_id, required=required)
    if not decision.allowed:
        raise HTTPException(403, decision.reason)
    return matter


def _task_priority(value: str | None) -> WorkflowTaskPriority:
    try:
        return WorkflowTaskPriority(value or "medium")
    except ValueError:
        return WorkflowTaskPriority.MEDIUM


async def seed_builtin_templates(db: AsyncSession) -> int:
    catalog = [
        {
            "code": "court-new-order", "trigger_type": "court.new_order",
            "name_en": "New court order review", "name_hi": "नए न्यायालय आदेश की समीक्षा",
            "description": "Creates a review task when an approved court-status snapshot indicates a new order/proceeding.",
            "actions_json": [
                {"type": "create_task", "title": "Review new court order", "priority": "high", "due_hours": 24},
                {"type": "notify", "subject": "New court order detected", "body": "A court-status snapshot indicates a new order/proceeding. Review the official source and update the matter."},
            ],
        },
        {
            "code": "court-hearing-change", "trigger_type": "court.hearing_date_changed",
            "name_en": "Hearing date change", "name_hi": "सुनवाई तिथि परिवर्तन",
            "description": "Creates a confirmation/preparation task when the next hearing date changes.",
            "actions_json": [
                {"type": "create_task", "title": "Confirm updated hearing date and prepare matter", "priority": "high", "due_hours": 12},
                {"type": "notify", "subject": "Hearing date changed", "body": "The tracked next-hearing date changed. Confirm it from the official court record and update the calendar."},
            ],
        },
        {
            "code": "court-status-change", "trigger_type": "court.case_status_changed",
            "name_en": "Case status change", "name_hi": "मामले की स्थिति परिवर्तन",
            "description": "Creates a review task when the tracked case status changes.",
            "actions_json": [
                {"type": "create_task", "title": "Review court case-status change", "priority": "medium", "due_hours": 24},
            ],
        },
        {
            "code": "deadline-due-soon", "trigger_type": "deadline.due_soon",
            "name_en": "Reviewed deadline due soon", "name_hi": "समीक्षित समयसीमा निकट",
            "description": "Creates an operational reminder only for lawyer-reviewed deadlines.",
            "actions_json": [
                {"type": "create_task", "title": "Deadline approaching", "priority": "high", "due_hours": 0},
                {"type": "notify", "subject": "Reviewed deadline approaching", "body": "A lawyer-reviewed matter deadline is approaching. Check compliance status."},
            ],
        },
    ]
    created = 0
    for item in catalog:
        exists = await db.scalar(select(WorkflowTemplate).where(
            WorkflowTemplate.organization_id.is_(None), WorkflowTemplate.code == item["code"], WorkflowTemplate.version == 1,
        ))
        if exists:
            continue
        db.add(WorkflowTemplate(organization_id=None, version=1, status=WorkflowTemplateStatus.ACTIVE,
            conditions_json={}, source_label="Junior Lawyer built-in operational workflow", **item))
        created += 1
    if created:
        await db.commit()
    return created


async def list_templates(db: AsyncSession, actor: ActorContext) -> list[WorkflowTemplate]:
    _require(actor, OPS_ROLES)
    stmt = select(WorkflowTemplate).where(
        or_(WorkflowTemplate.organization_id.is_(None), WorkflowTemplate.organization_id == actor.organization_id),
        WorkflowTemplate.status == WorkflowTemplateStatus.ACTIVE,
    ).order_by(WorkflowTemplate.code, WorkflowTemplate.version.desc())
    return list((await db.scalars(stmt)).all())


async def _default_recipient(db: AsyncSession, actor: ActorContext, matter_id: UUID | None) -> UUID:
    # The triggering lawyer remains the safest default: do not silently reveal a restricted matter to a partner.
    return actor.membership_id


async def _create_task_from_action(db: AsyncSession, actor: ActorContext, event: WorkflowEvent, run: WorkflowRun, action: dict) -> WorkflowTask:
    due_hours = int(action.get("due_hours", 24))
    due_at = event.occurred_at + timedelta(hours=due_hours) if due_hours >= 0 else None
    title = str(action.get("title") or event.event_type.replace(".", " ").title())
    detail = event.payload_json.get("summary") or event.payload_json.get("detail")
    row = WorkflowTask(
        organization_id=actor.organization_id, matter_id=event.matter_id, workflow_run_id=run.id,
        source_event_id=event.id, assigned_membership_id=await _default_recipient(db, actor, event.matter_id),
        created_by_user_id=actor.user_id, title=title, description=str(detail) if detail else None,
        priority=_task_priority(action.get("priority")), due_at=due_at,
        metadata_json={"automation": True, "trigger_type": event.event_type},
    )
    db.add(row); await db.flush(); return row


async def _notify_from_action(db: AsyncSession, actor: ActorContext, event: WorkflowEvent, task: WorkflowTask | None, action: dict, *, suffix: str) -> WorkflowNotification:
    dedupe = f"{event.dedupe_key}:notification:{suffix}"
    existing = await db.scalar(select(WorkflowNotification).where(
        WorkflowNotification.organization_id == actor.organization_id, WorkflowNotification.dedupe_key == dedupe,
    ))
    if existing:
        return existing
    row = WorkflowNotification(
        organization_id=actor.organization_id, matter_id=event.matter_id, task_id=task.id if task else None,
        recipient_membership_id=await _default_recipient(db, actor, event.matter_id),
        channel=NotificationChannel.IN_APP, status=NotificationStatus.PENDING,
        subject=str(action.get("subject") or "Junior Lawyer workflow update"),
        body=str(action.get("body") or event.payload_json.get("summary") or event.event_type),
        dedupe_key=dedupe, scheduled_at=utcnow(),
    )
    db.add(row); await db.flush(); return row


async def run_event_workflows(db: AsyncSession, actor: ActorContext, event: WorkflowEvent) -> list[WorkflowRun]:
    templates = list((await db.scalars(select(WorkflowTemplate).where(
        WorkflowTemplate.status == WorkflowTemplateStatus.ACTIVE,
        WorkflowTemplate.trigger_type == event.event_type,
        or_(WorkflowTemplate.organization_id.is_(None), WorkflowTemplate.organization_id == actor.organization_id),
    ).order_by(WorkflowTemplate.organization_id.desc().nullslast(), WorkflowTemplate.version.desc()))).all())
    runs: list[WorkflowRun] = []
    seen_codes: set[str] = set()
    for template in templates:
        if template.code in seen_codes:
            continue
        seen_codes.add(template.code)
        run = WorkflowRun(
            organization_id=actor.organization_id, matter_id=event.matter_id, template_id=template.id,
            trigger_event_id=event.id, status=WorkflowRunStatus.RUNNING, started_at=utcnow(), output_json={},
        )
        db.add(run); await db.flush()
        created_tasks: list[str] = []
        task: WorkflowTask | None = None
        try:
            for index, action in enumerate(template.actions_json or []):
                if action.get("type") == "create_task":
                    task = await _create_task_from_action(db, actor, event, run, action)
                    created_tasks.append(str(task.id))
                elif action.get("type") == "notify":
                    await _notify_from_action(db, actor, event, task, action, suffix=str(index))
            run.status = WorkflowRunStatus.COMPLETED
            run.completed_at = utcnow()
            run.output_json = {"tasks": created_tasks}
        except Exception as exc:
            run.status = WorkflowRunStatus.FAILED
            run.completed_at = utcnow()
            run.error_message = str(exc)[:2000]
        runs.append(run)
    await db.flush()
    return runs


async def emit_event(db: AsyncSession, actor: ActorContext, *, matter_id: UUID | None, event_type: str,
                     source_type: str | None, source_id: UUID | None, dedupe_key: str, payload: dict) -> WorkflowEvent:
    existing = await db.scalar(select(WorkflowEvent).where(
        WorkflowEvent.organization_id == actor.organization_id, WorkflowEvent.dedupe_key == dedupe_key,
    ))
    if existing:
        return existing
    event = WorkflowEvent(
        organization_id=actor.organization_id, matter_id=matter_id, event_type=event_type,
        source_type=source_type, source_id=source_id, dedupe_key=dedupe_key,
        occurred_at=utcnow(), payload_json=payload,
    )
    db.add(event); await db.flush()
    await run_event_workflows(db, actor, event)
    return event


async def create_task(db: AsyncSession, actor: ActorContext, payload: WorkflowTaskCreate) -> WorkflowTask:
    _require(actor, OPS_ROLES)
    if payload.matter_id:
        await _matter(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
    row = WorkflowTask(
        organization_id=actor.organization_id, created_by_user_id=actor.user_id,
        assigned_membership_id=payload.assigned_membership_id or actor.membership_id, **payload.model_dump(exclude={"assigned_membership_id"}),
    )
    db.add(row); await db.commit(); await db.refresh(row); return row


async def list_tasks(db: AsyncSession, actor: ActorContext, *, status: WorkflowTaskStatus | None = None, assigned_to_me: bool = False, limit: int = 200) -> list[WorkflowTask]:
    _require(actor, OPS_ROLES)
    visible = await visible_matter_ids(db, actor)
    stmt = select(WorkflowTask).where(WorkflowTask.organization_id == actor.organization_id).where(
        or_(WorkflowTask.matter_id.is_(None), WorkflowTask.matter_id.in_(visible) if visible else WorkflowTask.matter_id.is_(None))
    )
    if status:
        stmt = stmt.where(WorkflowTask.status == status)
    if assigned_to_me:
        stmt = stmt.where(WorkflowTask.assigned_membership_id == actor.membership_id)
    return list((await db.scalars(stmt.order_by(WorkflowTask.due_at.asc().nullslast(), WorkflowTask.created_at.desc()).limit(limit))).all())


async def update_task(db: AsyncSession, actor: ActorContext, task_id: UUID, payload: WorkflowTaskUpdate) -> WorkflowTask:
    _require(actor, OPS_ROLES)
    row = await db.get(WorkflowTask, task_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Workflow task not found")
    if row.matter_id:
        await _matter(db, actor, row.matter_id, required=MatterAccessLevel.WORK)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    if payload.status == WorkflowTaskStatus.DONE:
        row.completed_at = utcnow()
    elif payload.status and payload.status != WorkflowTaskStatus.DONE:
        row.completed_at = None
    await db.commit(); await db.refresh(row); return row


async def create_tracker(db: AsyncSession, actor: ActorContext, payload: CourtTrackerCreate) -> CourtCaseTracker:
    _require(actor, OPS_ROLES)
    matter = await _matter(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
    exists = await db.scalar(select(CourtCaseTracker).where(
        CourtCaseTracker.matter_id == payload.matter_id, CourtCaseTracker.source_kind == payload.source_kind,
    ))
    if exists:
        raise HTTPException(409, "This matter already has a tracker for that source")
    row = CourtCaseTracker(
        organization_id=actor.organization_id, matter_id=payload.matter_id,
        cnr_number=payload.cnr_number or matter.cnr_number, case_number=payload.case_number or matter.case_number,
        court_name=payload.court_name or matter.court_name, source_kind=payload.source_kind,
        bench_name=payload.bench_name, source_url=payload.source_url, config_json=payload.config_json,
    )
    db.add(row); await db.commit(); await db.refresh(row); return row


async def list_trackers(db: AsyncSession, actor: ActorContext, matter_id: UUID | None = None) -> list[CourtCaseTracker]:
    _require(actor, OPS_ROLES)
    visible = await visible_matter_ids(db, actor)
    if matter_id:
        await _matter(db, actor, matter_id)
    stmt = select(CourtCaseTracker).where(CourtCaseTracker.organization_id == actor.organization_id)
    if visible:
        stmt = stmt.where(CourtCaseTracker.matter_id.in_(visible))
    else:
        return []
    if matter_id:
        stmt = stmt.where(CourtCaseTracker.matter_id == matter_id)
    return list((await db.scalars(stmt.order_by(CourtCaseTracker.updated_at.desc()))).all())


def _snapshot_dict(row: CourtCaseSnapshot | None) -> dict | None:
    if not row:
        return None
    return {
        "case_status": row.case_status, "stage": row.stage, "next_hearing_date": row.next_hearing_date,
        "judge_or_bench": row.judge_or_bench, "order_count": row.order_count,
        "latest_order_date": row.latest_order_date, "latest_order_reference": row.latest_order_reference,
    }


async def capture_snapshot(db: AsyncSession, actor: ActorContext, tracker_id: UUID, payload: CourtSnapshotCreate) -> tuple[CourtCaseSnapshot, list[CourtCaseChange]]:
    _require(actor, OPS_ROLES)
    tracker = await db.get(CourtCaseTracker, tracker_id)
    if not tracker or tracker.organization_id != actor.organization_id:
        raise HTTPException(404, "Court tracker not found")
    await _matter(db, actor, tracker.matter_id, required=MatterAccessLevel.WORK)
    # First court capture should work without a separate setup ritual. Seeding is deterministic/idempotent.
    await seed_builtin_templates(db)
    previous = await db.scalar(select(CourtCaseSnapshot).where(CourtCaseSnapshot.tracker_id == tracker.id).order_by(CourtCaseSnapshot.captured_at.desc()).limit(1))
    current_data = payload.model_dump(exclude={"captured_at"})
    content_hash = stable_snapshot_hash(current_data)
    snapshot = CourtCaseSnapshot(
        tracker_id=tracker.id, captured_at=payload.captured_at or utcnow(), content_hash=content_hash,
        **current_data,
    )
    db.add(snapshot); await db.flush()
    changes: list[CourtCaseChange] = []
    for detected in detect_snapshot_changes(_snapshot_dict(previous), current_data):
        change = CourtCaseChange(
            organization_id=actor.organization_id, matter_id=tracker.matter_id, tracker_id=tracker.id,
            previous_snapshot_id=previous.id if previous else None, current_snapshot_id=snapshot.id,
            change_type=detected.change_type, severity=detected.severity, summary=detected.summary,
            old_value=detected.old_value, new_value=detected.new_value, detected_at=utcnow(),
        )
        db.add(change); await db.flush()
        event_type = f"court.{detected.change_type.value}"
        event = await emit_event(
            db, actor, matter_id=tracker.matter_id, event_type=event_type,
            source_type="court_case_change", source_id=change.id,
            dedupe_key=f"court-change:{tracker.id}:{snapshot.id}:{detected.change_type.value}",
            payload={"summary": detected.summary, "old_value": detected.old_value, "new_value": detected.new_value,
                     "tracker_id": str(tracker.id), "snapshot_id": str(snapshot.id)},
        )
        change.workflow_event_id = event.id
        changes.append(change)
    tracker.last_checked_at = snapshot.captured_at
    tracker.next_check_at = snapshot.captured_at + timedelta(hours=int(tracker.config_json.get("check_interval_hours", 24)))
    await db.commit(); await db.refresh(snapshot)
    return snapshot, changes


async def list_snapshots(db: AsyncSession, actor: ActorContext, tracker_id: UUID, limit: int = 50) -> list[CourtCaseSnapshot]:
    tracker = await db.get(CourtCaseTracker, tracker_id)
    if not tracker or tracker.organization_id != actor.organization_id:
        raise HTTPException(404, "Court tracker not found")
    await _matter(db, actor, tracker.matter_id)
    return list((await db.scalars(select(CourtCaseSnapshot).where(CourtCaseSnapshot.tracker_id == tracker_id).order_by(CourtCaseSnapshot.captured_at.desc()).limit(limit))).all())


async def list_changes(db: AsyncSession, actor: ActorContext, *, matter_id: UUID | None = None, unreviewed_only: bool = False, limit: int = 100) -> list[CourtCaseChange]:
    _require(actor, OPS_ROLES)
    visible = await visible_matter_ids(db, actor)
    if matter_id:
        await _matter(db, actor, matter_id)
    if not visible:
        return []
    stmt = select(CourtCaseChange).where(
        CourtCaseChange.organization_id == actor.organization_id, CourtCaseChange.matter_id.in_(visible),
    )
    if matter_id:
        stmt = stmt.where(CourtCaseChange.matter_id == matter_id)
    if unreviewed_only:
        stmt = stmt.where(CourtCaseChange.reviewed_at.is_(None))
    return list((await db.scalars(stmt.order_by(CourtCaseChange.detected_at.desc()).limit(limit))).all())


async def review_change(db: AsyncSession, actor: ActorContext, change_id: UUID) -> CourtCaseChange:
    row = await db.get(CourtCaseChange, change_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Court change not found")
    await _matter(db, actor, row.matter_id, required=MatterAccessLevel.WORK)
    row.reviewed_at = utcnow(); row.reviewed_by_user_id = actor.user_id
    await db.commit(); await db.refresh(row); return row


async def _find_escalation_recipient(db: AsyncSession, actor: ActorContext) -> UUID | None:
    row = await db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == actor.organization_id,
        OrganizationMembership.status == MembershipStatus.ACTIVE,
        OrganizationMembership.role.in_([OrganizationRole.PARTNER, OrganizationRole.OWNER, OrganizationRole.ADMIN]),
        OrganizationMembership.id != actor.membership_id,
    ).order_by(OrganizationMembership.created_at.asc()).limit(1))
    return row.id if row else None


async def run_due_sweep(db: AsyncSession, actor: ActorContext, payload: SweepRequest) -> dict[str, int]:
    _require(actor, OPS_ROLES)
    await seed_builtin_templates(db)
    now = utcnow(); today = now.date(); horizon = now + timedelta(hours=payload.horizon_hours)
    visible = await visible_matter_ids(db, actor)
    events = escalations = 0
    if visible:
        deadlines = list((await db.scalars(select(MatterDeadline).where(
            MatterDeadline.matter_id.in_(visible), MatterDeadline.reviewed_by_lawyer.is_(True),
            MatterDeadline.completed_at.is_(None), MatterDeadline.due_date >= today,
            MatterDeadline.due_date <= horizon.date(),
        ))).all())
        for row in deadlines:
            key = f"deadline-due-soon:{row.id}:{row.due_date.isoformat()}"
            before = await db.scalar(select(WorkflowEvent.id).where(WorkflowEvent.organization_id == actor.organization_id, WorkflowEvent.dedupe_key == key))
            await emit_event(db, actor, matter_id=row.matter_id, event_type="deadline.due_soon", source_type="matter_deadline", source_id=row.id,
                dedupe_key=key, payload={"summary": f"Reviewed deadline '{row.title}' is due {row.due_date.isoformat()}", "due_date": row.due_date.isoformat()})
            if not before: events += 1

    cutoff = now - timedelta(hours=payload.escalate_overdue_hours)
    overdue = list((await db.scalars(select(WorkflowTask).where(
        WorkflowTask.organization_id == actor.organization_id,
        WorkflowTask.status.in_([WorkflowTaskStatus.TODO, WorkflowTaskStatus.IN_PROGRESS]),
        WorkflowTask.due_at.is_not(None), WorkflowTask.due_at < cutoff,
    ))).all())
    visible_set = visible
    for task in overdue:
        if task.matter_id and task.matter_id not in visible_set:
            continue
        existing = await db.scalar(select(WorkflowEscalation).where(WorkflowEscalation.task_id == task.id, WorkflowEscalation.level == task.escalation_level + 1))
        if existing:
            continue
        recipient = await _find_escalation_recipient(db, actor)
        level = task.escalation_level + 1
        db.add(WorkflowEscalation(
            organization_id=actor.organization_id, task_id=task.id, level=level,
            reason=f"Task overdue by more than {payload.escalate_overdue_hours} hours",
            escalated_to_membership_id=recipient, escalated_at=now,
        ))
        task.escalation_level = level
        if recipient:
            dedupe = f"task-escalation:{task.id}:{level}"
            db.add(WorkflowNotification(
                organization_id=actor.organization_id, matter_id=task.matter_id, task_id=task.id,
                recipient_membership_id=recipient, channel=NotificationChannel.IN_APP,
                status=NotificationStatus.PENDING, subject="Overdue legal task escalated",
                body=f"{task.title} is overdue and requires supervision.", dedupe_key=dedupe, scheduled_at=now,
            ))
        escalations += 1
    await db.commit()
    return {"events_created": events, "escalations_created": escalations}


async def mark_notifications_sent(db: AsyncSession, actor: ActorContext, limit: int = 100) -> dict[str, int]:
    _require(actor, OPS_ROLES)
    rows = list((await db.scalars(select(WorkflowNotification).where(
        WorkflowNotification.organization_id == actor.organization_id,
        WorkflowNotification.status == NotificationStatus.PENDING,
        WorkflowNotification.scheduled_at <= utcnow(),
        or_(WorkflowNotification.recipient_membership_id.is_(None), WorkflowNotification.recipient_membership_id == actor.membership_id),
    ).order_by(WorkflowNotification.scheduled_at).limit(limit))).all())
    for row in rows:
        # IN_APP delivery means persisted/visible. External email stays a connector boundary.
        if row.channel in {NotificationChannel.IN_APP, NotificationChannel.CONSOLE}:
            row.status = NotificationStatus.SENT; row.sent_at = utcnow()
    await db.commit()
    return {"processed": len(rows), "sent": sum(1 for row in rows if row.status == NotificationStatus.SENT)}


async def list_notifications(db: AsyncSession, actor: ActorContext, *, unread_only: bool = False, limit: int = 100) -> list[WorkflowNotification]:
    stmt = select(WorkflowNotification).where(
        WorkflowNotification.organization_id == actor.organization_id,
        or_(WorkflowNotification.recipient_membership_id.is_(None), WorkflowNotification.recipient_membership_id == actor.membership_id),
    )
    if unread_only:
        stmt = stmt.where(WorkflowNotification.status == NotificationStatus.PENDING)
    return list((await db.scalars(stmt.order_by(WorkflowNotification.scheduled_at.desc()).limit(limit))).all())


async def get_preferences(db: AsyncSession, actor: ActorContext) -> OperationsPreference:
    row = await db.scalar(select(OperationsPreference).where(OperationsPreference.membership_id == actor.membership_id))
    if not row:
        row = OperationsPreference(organization_id=actor.organization_id, membership_id=actor.membership_id)
        db.add(row); await db.commit(); await db.refresh(row)
    return row


async def update_preferences(db: AsyncSession, actor: ActorContext, payload: OperationsPreferenceUpdate) -> OperationsPreference:
    row = await get_preferences(db, actor)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await db.commit(); await db.refresh(row); return row


async def daily_agenda(db: AsyncSession, actor: ActorContext, days: int = 7) -> list[dict]:
    _require(actor, OPS_ROLES)
    now = utcnow(); end = now + timedelta(days=days)
    visible = await visible_matter_ids(db, actor)
    matters = {}
    if visible:
        rows = (await db.scalars(select(Matter).where(Matter.id.in_(visible)))).all()
        matters = {row.id: row.title for row in rows}
    items: list[dict] = []

    tasks = await list_tasks(db, actor, assigned_to_me=True, limit=200)
    for row in tasks:
        if row.status in {WorkflowTaskStatus.DONE, WorkflowTaskStatus.CANCELLED}: continue
        if row.due_at and row.due_at <= end:
            items.append({"kind": "task", "id": row.id, "matter_id": row.matter_id, "matter_title": matters.get(row.matter_id),
                "when": row.due_at, "title": row.title, "status": row.status.value, "priority": row.priority.value,
                "requires_action": True, "detail": row.description})

    if visible:
        hearings = (await db.scalars(select(Hearing).where(
            Hearing.matter_id.in_(visible), Hearing.status == HearingStatus.SCHEDULED,
            Hearing.scheduled_for >= now, Hearing.scheduled_for <= end,
        ).order_by(Hearing.scheduled_for))).all()
        for row in hearings:
            items.append({"kind": "hearing", "id": row.id, "matter_id": row.matter_id, "matter_title": matters.get(row.matter_id),
                "when": row.scheduled_for, "title": row.purpose or "Court hearing", "status": row.status.value,
                "priority": "high", "requires_action": True, "detail": row.court_name})
        changes = (await db.scalars(select(CourtCaseChange).where(
            CourtCaseChange.matter_id.in_(visible), CourtCaseChange.reviewed_at.is_(None),
        ).order_by(CourtCaseChange.detected_at.desc()).limit(100))).all()
        for row in changes:
            items.append({"kind": "court_change", "id": row.id, "matter_id": row.matter_id, "matter_title": matters.get(row.matter_id),
                "when": row.detected_at, "title": row.summary, "status": "review", "priority": "high" if row.severity == ChangeSeverity.HIGH else "medium",
                "requires_action": True, "detail": f"{row.old_value or '—'} → {row.new_value or '—'}"})
    items.sort(key=lambda item: item["when"] or end)
    return items


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict[str, int]:
    _require(actor, OPS_ROLES)
    now = utcnow(); visible = await visible_matter_ids(db, actor)
    task_visibility = or_(WorkflowTask.matter_id.is_(None), WorkflowTask.matter_id.in_(visible)) if visible else WorkflowTask.matter_id.is_(None)
    task_base = [WorkflowTask.organization_id == actor.organization_id,
                 WorkflowTask.status.in_([WorkflowTaskStatus.TODO, WorkflowTaskStatus.IN_PROGRESS]), task_visibility]
    open_tasks = await db.scalar(select(func.count(WorkflowTask.id)).where(*task_base)) or 0
    overdue = await db.scalar(select(func.count(WorkflowTask.id)).where(*task_base, WorkflowTask.due_at.is_not(None), WorkflowTask.due_at < now)) or 0
    if visible:
        upcoming = await db.scalar(select(func.count(Hearing.id)).where(Hearing.matter_id.in_(visible), Hearing.status == HearingStatus.SCHEDULED, Hearing.scheduled_for >= now)) or 0
        changes = await db.scalar(select(func.count(CourtCaseChange.id)).where(CourtCaseChange.matter_id.in_(visible), CourtCaseChange.reviewed_at.is_(None))) or 0
        trackers = await db.scalar(select(func.count(CourtCaseTracker.id)).where(CourtCaseTracker.matter_id.in_(visible), CourtCaseTracker.status == CourtTrackerStatus.ACTIVE)) or 0
    else:
        upcoming = changes = trackers = 0
    pending_notifications = await db.scalar(select(func.count(WorkflowNotification.id)).where(
        WorkflowNotification.organization_id == actor.organization_id, WorkflowNotification.status == NotificationStatus.PENDING,
        or_(WorkflowNotification.recipient_membership_id.is_(None), WorkflowNotification.recipient_membership_id == actor.membership_id),
    )) or 0
    high = await db.scalar(select(func.count(WorkflowTask.id)).where(*task_base, WorkflowTask.priority.in_([WorkflowTaskPriority.HIGH, WorkflowTaskPriority.URGENT]))) or 0
    return {"open_tasks": open_tasks, "overdue_tasks": overdue, "upcoming_hearings": upcoming,
            "unreviewed_court_changes": changes, "pending_notifications": pending_notifications,
            "active_trackers": trackers, "high_priority_items": high}


async def partner_supervision(db: AsyncSession, actor: ActorContext) -> dict:
    _require(actor, PARTNER_ROLES)
    visible = await visible_matter_ids(db, actor); now = utcnow()
    tasks = list((await db.scalars(select(WorkflowTask).where(
        WorkflowTask.organization_id == actor.organization_id,
        WorkflowTask.status.in_([WorkflowTaskStatus.TODO, WorkflowTaskStatus.IN_PROGRESS]),
        or_(WorkflowTask.matter_id.is_(None), WorkflowTask.matter_id.in_(visible) if visible else WorkflowTask.matter_id.is_(None)),
    ))).all())
    membership_ids = {task.assigned_membership_id for task in tasks if task.assigned_membership_id}
    people: dict[UUID, tuple[str, str]] = {}
    if membership_ids:
        rows = (await db.execute(
            select(OrganizationMembership.id, OrganizationMembership.role, SecurityUser.display_name)
            .join(SecurityUser, SecurityUser.id == OrganizationMembership.user_id)
            .where(OrganizationMembership.id.in_(membership_ids))
        )).all()
        people = {row.id: (row.display_name, row.role.value) for row in rows}
    by_assignee: dict[str, dict] = {}
    for task in tasks:
        key = str(task.assigned_membership_id or "unassigned")
        person = people.get(task.assigned_membership_id) if task.assigned_membership_id else None
        bucket = by_assignee.setdefault(key, {"name": person[0] if person else "Unassigned", "role": person[1] if person else "", "open": 0, "overdue": 0, "high": 0})
        bucket["open"] += 1
        if task.due_at and task.due_at < now: bucket["overdue"] += 1
        if task.priority in {WorkflowTaskPriority.HIGH, WorkflowTaskPriority.URGENT}: bucket["high"] += 1
    return {"team": by_assignee, "total_open": len(tasks), "generated_at": now.isoformat()}
