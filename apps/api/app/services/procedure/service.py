from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.intelligence import ContradictionStatus, MatterContradiction, MatterFact
from app.models.matter import Matter
from app.models.security import MatterAccessLevel, OrganizationRole
from app.services.security.context import get_current_actor
from app.services.security.permissions import decide_matter_access, visible_matter_ids
from app.models.procedure import (
    ComplianceStatus,
    DeadlineRule,
    DeadlineStatus,
    DirectionStatus,
    Hearing,
    HearingDirection,
    HearingStatus,
    MatterCompliance,
    MatterDeadline,
    MatterProcedure,
    MatterProcedureStatus,
    ProcedurePack,
    ProcedurePackStatus,
    ProcedureStep,
)
from app.schemas.procedure import (
    AttachProcedureRequest,
    ComplianceUpdate,
    DeadlineUpdate,
    DirectionCreate,
    DirectionUpdate,
    HearingCreate,
    HearingUpdate,
    MatterDeadlineCreate,
    ProcedurePackCreate,
    RuleDeadlineCreate,
)
from app.services.procedure.calculator import calculate_deadline
from app.services.procedure.catalog import BUILTIN_PACKS
from app.services.procedure.extractor import extract_directions


DISCLAIMER = (
    "Procedural and limitation calculations are workflow aids only. Verify the controlling law, "
    "court rules, exclusions, extensions, condonation provisions and the competent authority before acting."
)


async def _require_matter_access(
    db: AsyncSession, matter_id: UUID, *, required: MatterAccessLevel = MatterAccessLevel.VIEW
) -> None:
    actor = get_current_actor()
    if actor is None:
        return
    decision = await decide_matter_access(db, actor, matter_id, required=required)
    if not decision.allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)


def _pack_options():
    return (selectinload(ProcedurePack.steps), selectinload(ProcedurePack.deadline_rules))


def _hearing_options():
    return (selectinload(Hearing.directions),)


def _procedure_options():
    return (selectinload(MatterProcedure.pack), selectinload(MatterProcedure.compliances), selectinload(MatterProcedure.deadlines))


def deadline_status(row: MatterDeadline, today: date | None = None) -> DeadlineStatus:
    if row.completed_at:
        return DeadlineStatus.COMPLETED
    if not row.reviewed_by_lawyer:
        return DeadlineStatus.REVIEW
    today = today or date.today()
    if row.due_date < today:
        return DeadlineStatus.OVERDUE
    if row.due_date == today:
        return DeadlineStatus.DUE_TODAY
    return DeadlineStatus.UPCOMING


async def create_pack(db: AsyncSession, payload: ProcedurePackCreate) -> ProcedurePack:
    actor = get_current_actor()
    if actor is not None and actor.role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}:
        raise HTTPException(status_code=403, detail="Procedure-pack management is not permitted for this role")
    existing = await db.scalar(select(ProcedurePack).where(ProcedurePack.code == payload.code, ProcedurePack.version == payload.version))
    if existing:
        raise HTTPException(status_code=409, detail="Procedure pack code/version already exists")
    if payload.status == ProcedurePackStatus.ACTIVE:
        if not payload.verified or not payload.source_name:
            raise HTTPException(status_code=400, detail="An active procedure pack must be verified and source-attributed")
        unsafe_rules = [rule.code for rule in payload.deadline_rules if not rule.verified or not rule.source_name or not rule.source_citation]
        if unsafe_rules:
            raise HTTPException(status_code=400, detail={"message": "Active deadline rules require verified source attribution", "rules": unsafe_rules})
    pack = ProcedurePack(
        code=payload.code, name_en=payload.name_en, name_hi=payload.name_hi,
        jurisdiction=payload.jurisdiction, proceeding_type=payload.proceeding_type,
        court_level=payload.court_level, description=payload.description, version=payload.version,
        status=payload.status, effective_from=payload.effective_from, effective_to=payload.effective_to,
        source_name=payload.source_name, source_url=payload.source_url,
        source_citation=payload.source_citation, verified=payload.verified,
        metadata_json=payload.metadata_json,
    )
    db.add(pack)
    await db.flush()
    for step in payload.steps:
        db.add(ProcedureStep(pack_id=pack.id, **step.model_dump()))
    for rule in payload.deadline_rules:
        db.add(DeadlineRule(pack_id=pack.id, **rule.model_dump()))
    await db.commit()
    return await get_pack(db, pack.id)


async def seed_builtin_packs(db: AsyncSession) -> int:
    created = 0
    for code, definition in BUILTIN_PACKS.items():
        existing = await db.scalar(select(ProcedurePack).where(ProcedurePack.code == code, ProcedurePack.version == 1))
        if existing:
            continue
        pack = ProcedurePack(
            code=code, name_en=definition["name_en"], name_hi=definition["name_hi"],
            jurisdiction=definition["jurisdiction"], proceeding_type=definition["proceeding_type"],
            court_level=definition["court_level"], description=definition["description"], version=1,
            status=ProcedurePackStatus.DRAFT, source_name=definition["source_name"],
            source_citation=definition["source_citation"], verified=definition["verified"],
            metadata_json={"builtin": True, "legal_deadlines_included": False},
        )
        db.add(pack)
        await db.flush()
        for step in definition["steps"]:
            db.add(ProcedureStep(
                pack_id=pack.id, code=step["code"], sequence=step["sequence"],
                name_en=step["name_en"], name_hi=step["name_hi"], required=step["required"],
                checklist_json=step["checklist"], dependency_codes_json=[], metadata_json={"builtin": True},
            ))
        created += 1
    await db.commit()
    return created


async def list_packs(db: AsyncSession) -> list[ProcedurePack]:
    return list((await db.scalars(select(ProcedurePack).options(*_pack_options()).order_by(ProcedurePack.name_en, ProcedurePack.version.desc()))).unique().all())


async def get_pack(db: AsyncSession, pack_id: UUID) -> ProcedurePack:
    pack = await db.scalar(select(ProcedurePack).where(ProcedurePack.id == pack_id).options(*_pack_options()))
    if not pack:
        raise HTTPException(status_code=404, detail="Procedure pack not found")
    return pack


async def attach_procedure(db: AsyncSession, matter_id: UUID, payload: AttachProcedureRequest) -> MatterProcedure:
    matter = await db.get(Matter, matter_id)
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    await _require_matter_access(db, matter_id, required=MatterAccessLevel.WORK)
    pack = await get_pack(db, payload.pack_id)
    snapshot = {
        "code": pack.code, "name_en": pack.name_en, "version": pack.version,
        "verified": pack.verified, "source_name": pack.source_name,
        "source_url": pack.source_url, "source_citation": pack.source_citation,
    }
    row = MatterProcedure(
        matter_id=matter_id, pack_id=pack.id, status=MatterProcedureStatus.ACTIVE,
        started_on=payload.started_on or date.today(), pack_snapshot_json=snapshot, notes=payload.notes,
    )
    db.add(row)
    await db.flush()
    for step in pack.steps:
        db.add(MatterCompliance(
            matter_procedure_id=row.id, procedure_step_id=step.id,
            title=step.name_en, description=step.description, status=ComplianceStatus.PENDING,
            metadata_json={"step_code": step.code, "sequence": step.sequence, "required": step.required, "checklist": step.checklist_json},
        ))
    await db.commit()
    return await get_matter_procedure(db, row.id)


async def get_matter_procedure(db: AsyncSession, procedure_id: UUID) -> MatterProcedure:
    row = await db.scalar(select(MatterProcedure).where(MatterProcedure.id == procedure_id).options(*_procedure_options()))
    if not row:
        raise HTTPException(status_code=404, detail="Matter procedure not found")
    await _require_matter_access(db, row.matter_id, required=MatterAccessLevel.VIEW)
    return row


async def list_matter_procedures(db: AsyncSession, matter_id: UUID) -> list[MatterProcedure]:
    await _require_matter_access(db, matter_id, required=MatterAccessLevel.VIEW)
    return list((await db.scalars(select(MatterProcedure).where(MatterProcedure.matter_id == matter_id).options(*_procedure_options()).order_by(MatterProcedure.created_at.desc()))).unique().all())


async def update_compliance(db: AsyncSession, compliance_id: UUID, payload: ComplianceUpdate) -> MatterCompliance:
    row = await db.get(MatterCompliance, compliance_id)
    if not row:
        raise HTTPException(status_code=404, detail="Compliance item not found")
    procedure = await db.get(MatterProcedure, row.matter_procedure_id)
    if procedure:
        await _require_matter_access(db, procedure.matter_id, required=MatterAccessLevel.WORK)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    if payload.status == ComplianceStatus.COMPLETED and not row.completed_at:
        row.completed_at = datetime.now(timezone.utc)
    elif payload.status is not None and payload.status != ComplianceStatus.COMPLETED:
        row.completed_at = None
    await db.commit()
    await db.refresh(row)
    return row


async def create_manual_deadline(db: AsyncSession, matter_id: UUID, payload: MatterDeadlineCreate) -> MatterDeadline:
    if not await db.get(Matter, matter_id):
        raise HTTPException(status_code=404, detail="Matter not found")
    await _require_matter_access(db, matter_id, required=MatterAccessLevel.WORK)
    calc = calculate_deadline(
        payload.trigger_date, offset_days=payload.offset_days, day_basis=payload.day_basis,
        count_from_next_day=payload.count_from_next_day, adjustment=payload.adjustment,
        holidays=set(payload.holidays),
    )
    authority = {
        "source_name": payload.source_name, "source_url": payload.source_url,
        "source_citation": payload.source_citation, "verified": False,
        "note": "Manual calculation; legal authority not verified by the system.",
    }
    row = MatterDeadline(
        matter_id=matter_id, matter_procedure_id=payload.matter_procedure_id,
        title=payload.title, trigger_type=payload.trigger_type, trigger_id=payload.trigger_id,
        trigger_date=payload.trigger_date, calculated_date=calc.calculated_date, due_date=calc.due_date,
        status=DeadlineStatus.REVIEW, reviewed_by_lawyer=False,
        calculation_json=calc.as_dict(), authority_json=authority, notes=payload.notes,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def create_rule_deadline(db: AsyncSession, matter_id: UUID, payload: RuleDeadlineCreate) -> MatterDeadline:
    if not await db.get(Matter, matter_id):
        raise HTTPException(status_code=404, detail="Matter not found")
    await _require_matter_access(db, matter_id, required=MatterAccessLevel.WORK)
    rule = await db.get(DeadlineRule, payload.deadline_rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Deadline rule not found")
    if rule.effective_from and payload.trigger_date < rule.effective_from:
        raise HTTPException(status_code=400, detail="Rule was not effective on trigger date")
    if rule.effective_to and payload.trigger_date > rule.effective_to:
        raise HTTPException(status_code=400, detail="Rule was no longer effective on trigger date")
    calc = calculate_deadline(
        payload.trigger_date, offset_days=rule.offset_days, day_basis=rule.day_basis,
        count_from_next_day=rule.count_from_next_day, adjustment=rule.adjustment,
        holidays=set(payload.holidays),
    )
    authority = {
        "source_name": rule.source_name, "source_url": rule.source_url,
        "source_citation": rule.source_citation, "verified": rule.verified,
        "rule_code": rule.code, "rule_version": None,
        "requires_lawyer_review": rule.requires_lawyer_review,
    }
    reviewed = rule.verified and not rule.requires_lawyer_review
    row = MatterDeadline(
        matter_id=matter_id, matter_procedure_id=payload.matter_procedure_id,
        deadline_rule_id=rule.id, title=rule.name_en, trigger_type=payload.trigger_type,
        trigger_id=payload.trigger_id, trigger_date=payload.trigger_date,
        calculated_date=calc.calculated_date, due_date=calc.due_date,
        reviewed_by_lawyer=reviewed, calculation_json=calc.as_dict(), authority_json=authority,
        notes=payload.notes,
    )
    row.status = deadline_status(row)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_deadlines(db: AsyncSession, matter_id: UUID | None = None) -> list[MatterDeadline]:
    stmt = select(MatterDeadline)
    actor = get_current_actor()
    if matter_id:
        await _require_matter_access(db, matter_id, required=MatterAccessLevel.VIEW)
        stmt = stmt.where(MatterDeadline.matter_id == matter_id)
    elif actor is not None:
        visible = await visible_matter_ids(db, actor)
        if not visible:
            return []
        stmt = stmt.where(MatterDeadline.matter_id.in_(visible))
    rows = list((await db.scalars(stmt.order_by(MatterDeadline.due_date, MatterDeadline.created_at))).all())
    dirty = False
    for row in rows:
        current = deadline_status(row)
        if row.status != current:
            row.status = current
            dirty = True
    if dirty:
        await db.commit()
    return rows


async def update_deadline(db: AsyncSession, deadline_id: UUID, payload: DeadlineUpdate) -> MatterDeadline:
    row = await db.get(MatterDeadline, deadline_id)
    if not row:
        raise HTTPException(status_code=404, detail="Deadline not found")
    await _require_matter_access(db, row.matter_id, required=MatterAccessLevel.WORK)
    data = payload.model_dump(exclude_unset=True)
    if "completed" in data:
        row.completed_at = datetime.now(timezone.utc) if data.pop("completed") else None
    for key, value in data.items():
        setattr(row, key, value)
    row.status = deadline_status(row)
    await db.commit()
    await db.refresh(row)
    return row


async def create_hearing(db: AsyncSession, payload: HearingCreate) -> Hearing:
    matter = await db.get(Matter, payload.matter_id)
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    await _require_matter_access(db, payload.matter_id, required=MatterAccessLevel.WORK)
    data = payload.model_dump()
    if not data.get("court_name"):
        data["court_name"] = matter.court_name
    row = Hearing(**data, status=HearingStatus.SCHEDULED, metadata_json={"source": "manual"})
    db.add(row)
    await db.commit()
    return await get_hearing(db, row.id)


async def get_hearing(db: AsyncSession, hearing_id: UUID) -> Hearing:
    row = await db.scalar(select(Hearing).where(Hearing.id == hearing_id).options(*_hearing_options()))
    if not row:
        raise HTTPException(status_code=404, detail="Hearing not found")
    await _require_matter_access(db, row.matter_id, required=MatterAccessLevel.VIEW)
    return row


async def list_hearings(db: AsyncSession, matter_id: UUID | None = None) -> list[Hearing]:
    stmt = select(Hearing).options(*_hearing_options())
    actor = get_current_actor()
    if matter_id:
        await _require_matter_access(db, matter_id, required=MatterAccessLevel.VIEW)
        stmt = stmt.where(Hearing.matter_id == matter_id)
    elif actor is not None:
        visible = await visible_matter_ids(db, actor)
        if not visible:
            return []
        stmt = stmt.where(Hearing.matter_id.in_(visible))
    return list((await db.scalars(stmt.order_by(Hearing.scheduled_for))).unique().all())


async def update_hearing(db: AsyncSession, hearing_id: UUID, payload: HearingUpdate) -> Hearing:
    row = await get_hearing(db, hearing_id)
    await _require_matter_access(db, row.matter_id, required=MatterAccessLevel.WORK)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await db.commit()
    return await get_hearing(db, hearing_id)


async def create_direction(db: AsyncSession, hearing_id: UUID, payload: DirectionCreate) -> HearingDirection:
    hearing = await get_hearing(db, hearing_id)
    await _require_matter_access(db, hearing.matter_id, required=MatterAccessLevel.WORK)
    row = HearingDirection(
        hearing_id=hearing.id, matter_id=hearing.matter_id, text=payload.text,
        due_date=payload.due_date, source_document_id=payload.source_document_id,
        page_number=payload.page_number, extracted=False, confidence=100,
        requires_review=payload.requires_review, metadata_json={"source": "manual"},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_direction(db: AsyncSession, direction_id: UUID, payload: DirectionUpdate) -> HearingDirection:
    row = await db.get(HearingDirection, direction_id)
    if not row:
        raise HTTPException(status_code=404, detail="Hearing direction not found")
    await _require_matter_access(db, row.matter_id, required=MatterAccessLevel.WORK)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


async def extract_directions_from_document(db: AsyncSession, hearing_id: UUID, document_id: UUID, order_date: date | None = None) -> list[HearingDirection]:
    hearing = await get_hearing(db, hearing_id)
    await _require_matter_access(db, hearing.matter_id, required=MatterAccessLevel.WORK)
    document = await db.get(Document, document_id)
    if not document or document.matter_id != hearing.matter_id:
        raise HTTPException(status_code=404, detail="Document not found in this matter")
    pages = list((await db.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number))).all())
    created: list[HearingDirection] = []
    base_date = order_date or hearing.scheduled_for.date()
    for page in pages:
        for extracted in extract_directions(page.text, order_date=base_date):
            row = HearingDirection(
                hearing_id=hearing.id, matter_id=hearing.matter_id, text=extracted.text,
                due_date=extracted.due_date, source_document_id=document_id, page_number=page.page_number,
                extracted=True, confidence=extracted.confidence, requires_review=True,
                metadata_json=extracted.metadata,
            )
            db.add(row)
            created.append(row)
    await db.commit()
    for row in created:
        await db.refresh(row)
    return created


async def procedure_stats(db: AsyncSession) -> dict:
    today = date.today()
    now = datetime.now(timezone.utc)
    actor = get_current_actor()
    visible_ids: list[UUID] | None = None
    if actor is not None:
        visible_ids = await visible_matter_ids(db, actor)
        if not visible_ids:
            return {
                "active_procedures": 0,
                "pending_compliances": 0,
                "upcoming_deadlines": 0,
                "overdue_deadlines": 0,
                "unreviewed_deadlines": 0,
                "upcoming_hearings": 0,
                "open_directions": 0,
            }

    procedure_filters = [MatterProcedure.status == MatterProcedureStatus.ACTIVE]
    deadline_base = [MatterDeadline.completed_at.is_(None)]
    hearing_filters = [Hearing.status == HearingStatus.SCHEDULED, Hearing.scheduled_for >= now]
    direction_filters = [HearingDirection.status == DirectionStatus.OPEN]
    if visible_ids is not None:
        procedure_filters.append(MatterProcedure.matter_id.in_(visible_ids))
        deadline_base.append(MatterDeadline.matter_id.in_(visible_ids))
        hearing_filters.append(Hearing.matter_id.in_(visible_ids))
        direction_filters.append(HearingDirection.matter_id.in_(visible_ids))

    active_procedures = await db.scalar(
        select(func.count()).select_from(MatterProcedure).where(*procedure_filters)
    ) or 0

    pending_query = (
        select(func.count())
        .select_from(MatterCompliance)
        .join(MatterProcedure, MatterCompliance.matter_procedure_id == MatterProcedure.id)
        .where(MatterCompliance.status.in_([ComplianceStatus.PENDING, ComplianceStatus.IN_PROGRESS]))
    )
    if visible_ids is not None:
        pending_query = pending_query.where(MatterProcedure.matter_id.in_(visible_ids))
    pending_compliances = await db.scalar(pending_query) or 0

    upcoming_deadlines = await db.scalar(
        select(func.count()).select_from(MatterDeadline).where(
            *deadline_base, MatterDeadline.reviewed_by_lawyer.is_(True), MatterDeadline.due_date >= today
        )
    ) or 0
    overdue_deadlines = await db.scalar(
        select(func.count()).select_from(MatterDeadline).where(
            *deadline_base, MatterDeadline.reviewed_by_lawyer.is_(True), MatterDeadline.due_date < today
        )
    ) or 0
    unreviewed_deadlines = await db.scalar(
        select(func.count()).select_from(MatterDeadline).where(
            *deadline_base, MatterDeadline.reviewed_by_lawyer.is_(False)
        )
    ) or 0
    upcoming_hearings = await db.scalar(
        select(func.count()).select_from(Hearing).where(*hearing_filters)
    ) or 0
    open_directions = await db.scalar(
        select(func.count()).select_from(HearingDirection).where(*direction_filters)
    ) or 0
    return {
        "active_procedures": active_procedures,
        "pending_compliances": pending_compliances,
        "upcoming_deadlines": upcoming_deadlines,
        "overdue_deadlines": overdue_deadlines,
        "unreviewed_deadlines": unreviewed_deadlines,
        "upcoming_hearings": upcoming_hearings,
        "open_directions": open_directions,
    }


async def agenda(db: AsyncSession, *, matter_id: UUID | None = None, days: int = 30) -> list[dict]:
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days)
    items: list[dict] = []
    deadlines = await list_deadlines(db, matter_id)
    for row in deadlines:
        if row.completed_at:
            continue
        when = datetime.combine(row.due_date, time(9, 0), tzinfo=timezone.utc)
        if now <= when <= horizon:
            items.append({
                "kind": "deadline", "id": row.id, "matter_id": row.matter_id,
                "title": row.title, "when": when, "status": row.status.value,
                "requires_review": not row.reviewed_by_lawyer,
                "metadata": {"authority": row.authority_json},
            })
    hearings = await list_hearings(db, matter_id)
    for row in hearings:
        if row.status not in {HearingStatus.SCHEDULED, HearingStatus.ADJOURNED}:
            continue
        scheduled = row.scheduled_for if row.scheduled_for.tzinfo else row.scheduled_for.replace(tzinfo=timezone.utc)
        if now <= scheduled <= horizon:
            items.append({
                "kind": "hearing", "id": row.id, "matter_id": row.matter_id,
                "title": row.purpose or "Hearing", "when": scheduled,
                "status": row.status.value, "requires_review": False,
                "metadata": {"court_name": row.court_name, "judge_or_bench": row.judge_or_bench},
            })
    return sorted(items, key=lambda item: item["when"])[:200]


async def hearing_brief(db: AsyncSession, hearing_id: UUID) -> dict:
    hearing = await get_hearing(db, hearing_id)
    matter = await db.get(Matter, hearing.matter_id)
    previous = await db.scalar(
        select(Hearing).where(Hearing.matter_id == hearing.matter_id, Hearing.scheduled_for < hearing.scheduled_for).options(*_hearing_options()).order_by(Hearing.scheduled_for.desc()).limit(1)
    )
    deadlines = [item for item in await list_deadlines(db, hearing.matter_id) if item.completed_at is None and item.due_date >= date.today()][:10]
    procedures = await list_matter_procedures(db, hearing.matter_id)
    pending_compliances = []
    for procedure in procedures:
        for item in procedure.compliances:
            if item.status in {ComplianceStatus.PENDING, ComplianceStatus.IN_PROGRESS}:
                pending_compliances.append({"id": str(item.id), "title": item.title, "status": item.status.value, "due_date": item.due_date.isoformat() if item.due_date else None})
    facts = list((await db.scalars(select(MatterFact).where(MatterFact.matter_id == hearing.matter_id).order_by(MatterFact.confidence.desc()).limit(12))).all())
    contradictions = list((await db.scalars(select(MatterContradiction).where(MatterContradiction.matter_id == hearing.matter_id, MatterContradiction.status == ContradictionStatus.OPEN).limit(10))).all())
    return {
        "matter_id": hearing.matter_id,
        "matter_title": matter.title if matter else "Matter",
        "hearing": hearing,
        "previous_hearing": previous,
        "open_directions": [item for item in hearing.directions if item.status == DirectionStatus.OPEN],
        "upcoming_deadlines": deadlines,
        "pending_compliances": pending_compliances,
        "key_facts": [{"id": str(item.id), "label": item.label, "value": item.value_text, "confidence": item.confidence, "status": item.status.value} for item in facts],
        "open_contradictions": [{"id": str(item.id), "label": item.label, "severity": item.severity.value, "explanation": item.explanation} for item in contradictions],
        "disclaimer": DISCLAIMER,
    }
