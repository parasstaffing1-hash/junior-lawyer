from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import (
    AnalyticsGoal,
    AnalyticsGoalProgress,
    AnalyticsGoalStatus,
    AnalyticsMetricDefinition,
    AnalyticsMetricValue,
    AnalyticsPreference,
    AnalyticsRiskSeverity,
    AnalyticsRiskSignal,
    AnalyticsRiskStatus,
    AnalyticsScope,
    AnalyticsSnapshot,
    ClientHealthSnapshot,
    GoalComparison,
    MatterHealthSnapshot,
    MemberPerformanceSnapshot,
    MetricDirection,
    SnapshotKind,
)
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentStatus
from app.models.contract import Contract, ContractRisk, ContractRiskLevel, ContractRiskStatus
from app.models.crm import Client, ClientAccessGrant, ClientCommunication, ClientSecurityProfile, MatterClientLink, TimeEntry, TimeEntryStatus
from app.models.drafting import DraftFindingLevel, DraftFindingStatus, LegalDraft, LegalDraftFinding, LegalDraftStatus
from app.models.evidence import EvidenceGap, GapStatus
from app.models.intelligence import ContradictionStatus, MatterContradiction
from app.models.knowledge import KnowledgeAsset, KnowledgeAssetStatus
from app.models.matter import Matter, MatterStatus
from app.models.operations import CourtCaseChange, WorkflowTask, WorkflowTaskPriority, WorkflowTaskStatus
from app.models.portal import ClientPortalRequest, PortalRequestStatus
from app.models.procedure import DeadlineStatus, Hearing, HearingStatus, MatterDeadline
from app.models.security import AccessEffect, ConfidentialityLevel, MatterAccessMode, OrganizationMembership, OrganizationRole, SecurityUser
from app.services.analytics.calculator import (
    DEFAULT_HEALTH_WEIGHTS,
    DEFAULT_THRESHOLDS,
    MatterHealthInput,
    classify_health,
    goal_progress,
    matter_health_score,
    percentage,
    stable_payload_hash,
    workload_score,
)
from app.services.security.context import ActorContext
from app.services.security.permissions import visible_client_ids, visible_matter_ids


MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}
FINANCE_ROLES = MANAGER_ROLES | {OrganizationRole.BILLING}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return utcnow().date()


async def _visible_finance_client_ids(db: AsyncSession, actor: ActorContext) -> set[UUID]:
    if actor.role != OrganizationRole.BILLING:
        return await visible_client_ids(db, actor)
    ids = list((await db.scalars(select(Client.id).where(Client.organization_id == actor.organization_id))).all())
    visible: set[UUID] = set()
    for client_id in ids:
        profile = await db.scalar(select(ClientSecurityProfile).where(ClientSecurityProfile.client_id == client_id))
        if profile and (profile.access_mode == MatterAccessMode.EXPLICIT or profile.classification == ConfidentialityLevel.ETHICAL_WALL):
            grant = await db.scalar(select(ClientAccessGrant).where(
                ClientAccessGrant.client_id == client_id,
                ClientAccessGrant.membership_id == actor.membership_id,
                ClientAccessGrant.effect == AccessEffect.ALLOW,
            ))
            if not grant:
                continue
        visible.add(client_id)
    return visible


def _require(actor: ActorContext, allowed: set[OrganizationRole], message: str = "Insufficient analytics permission") -> None:
    if actor.role not in allowed:
        raise HTTPException(403, message)


async def get_preferences(db: AsyncSession, actor: ActorContext) -> AnalyticsPreference:
    row = await db.scalar(select(AnalyticsPreference).where(AnalyticsPreference.organization_id == actor.organization_id))
    if row:
        return row
    row = AnalyticsPreference(
        organization_id=actor.organization_id,
        health_weights_json=dict(DEFAULT_HEALTH_WEIGHTS),
        thresholds_json=dict(DEFAULT_THRESHOLDS),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_preferences(db: AsyncSession, actor: ActorContext, values: dict) -> AnalyticsPreference:
    _require(actor, MANAGER_ROLES)
    row = await get_preferences(db, actor)
    for key, value in values.items():
        if value is not None:
            setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


async def seed_metric_definitions(db: AsyncSession, actor: ActorContext) -> int:
    _require(actor, MANAGER_ROLES)
    catalog = [
        ("matter_health_avg", "Average matter health", "औसत मामला स्वास्थ्य", "score", MetricDirection.HIGHER_BETTER, "Average deterministic health score across visible active matters."),
        ("at_risk_matters", "At-risk matters", "जोखिम वाले मामले", "count", MetricDirection.LOWER_BETTER, "Visible active matters with health below 60."),
        ("overdue_tasks", "Overdue tasks", "अतिदेय कार्य", "count", MetricDirection.LOWER_BETTER, "Open visible workflow tasks past their due time."),
        ("deadlines_due_7d", "Reviewed deadlines due in 7 days", "7 दिनों में समीक्षित समयसीमाएँ", "count", MetricDirection.LOWER_BETTER, "Lawyer-reviewed visible deadlines due within seven days."),
        ("draft_health_avg", "Draft health", "ड्राफ्ट स्वास्थ्य", "score", MetricDirection.HIGHER_BETTER, "Average health score of visible legal drafts."),
        ("approved_drafts_30d", "Approved drafts (30d)", "स्वीकृत ड्राफ्ट (30 दिन)", "count", MetricDirection.HIGHER_BETTER, "Visible legal drafts approved in the rolling window."),
        ("knowledge_reuse", "Precedent reuse", "नज़ीर पुन: उपयोग", "uses", MetricDirection.HIGHER_BETTER, "Recorded usage count across approved firm knowledge assets."),
        ("outstanding_amount", "Outstanding receivables", "बकाया प्राप्तियाँ", "currency", MetricDirection.LOWER_BETTER, "Outstanding issued invoice amount within the user's permitted financial scope."),
        ("overdue_amount", "Overdue receivables", "अतिदेय प्राप्तियाँ", "currency", MetricDirection.LOWER_BETTER, "Outstanding amount past invoice due date."),
        ("collection_rate_30d", "Collection rate (30d)", "संग्रह दर (30 दिन)", "percent", MetricDirection.HIGHER_BETTER, "Cleared payments divided by invoices issued in the rolling window."),
    ]
    created = 0
    for key, en, hi, unit, direction, description in catalog:
        exists = await db.scalar(select(AnalyticsMetricDefinition).where(
            AnalyticsMetricDefinition.organization_id == actor.organization_id,
            AnalyticsMetricDefinition.metric_key == key,
        ))
        if exists:
            continue
        db.add(AnalyticsMetricDefinition(
            organization_id=actor.organization_id,
            metric_key=key,
            name_en=en,
            name_hi=hi,
            description=description,
            unit=unit,
            direction=direction,
            formula_json={"engine": "deterministic", "version": 1},
        ))
        created += 1
    if created:
        await db.commit()
    return created


async def list_metric_definitions(db: AsyncSession, actor: ActorContext) -> list[AnalyticsMetricDefinition]:
    return list((await db.scalars(select(AnalyticsMetricDefinition).where(
        or_(AnalyticsMetricDefinition.organization_id.is_(None), AnalyticsMetricDefinition.organization_id == actor.organization_id),
        AnalyticsMetricDefinition.active.is_(True),
    ).order_by(AnalyticsMetricDefinition.metric_key))).all())


async def _matter_health(db: AsyncSession, matter_id: UUID, weights: dict) -> dict:
    now = utcnow()
    today = now.date()
    due_7d = today + timedelta(days=7)

    open_statuses = [WorkflowTaskStatus.TODO, WorkflowTaskStatus.IN_PROGRESS]
    overdue_tasks = int(await db.scalar(select(func.count(WorkflowTask.id)).where(
        WorkflowTask.matter_id == matter_id,
        WorkflowTask.status.in_(open_statuses),
        WorkflowTask.due_at.is_not(None),
        WorkflowTask.due_at < now,
    )) or 0)
    high_tasks = int(await db.scalar(select(func.count(WorkflowTask.id)).where(
        WorkflowTask.matter_id == matter_id,
        WorkflowTask.status.in_(open_statuses),
        WorkflowTask.priority.in_([WorkflowTaskPriority.HIGH, WorkflowTaskPriority.URGENT]),
    )) or 0)
    deadlines = int(await db.scalar(select(func.count(MatterDeadline.id)).where(
        MatterDeadline.matter_id == matter_id,
        MatterDeadline.reviewed_by_lawyer.is_(True),
        MatterDeadline.status != DeadlineStatus.COMPLETED,
        MatterDeadline.due_date >= today,
        MatterDeadline.due_date <= due_7d,
    )) or 0)
    contradictions = int(await db.scalar(select(func.count(MatterContradiction.id)).where(
        MatterContradiction.matter_id == matter_id,
        MatterContradiction.status == ContradictionStatus.OPEN,
    )) or 0)
    high_findings = int(await db.scalar(select(func.count(LegalDraftFinding.id)).join(
        LegalDraft, LegalDraft.id == LegalDraftFinding.draft_id
    ).where(
        LegalDraft.matter_id == matter_id,
        LegalDraftFinding.status == DraftFindingStatus.OPEN,
        LegalDraftFinding.level == DraftFindingLevel.HIGH,
    )) or 0)
    court_changes = int(await db.scalar(select(func.count(CourtCaseChange.id)).where(
        CourtCaseChange.matter_id == matter_id,
        CourtCaseChange.reviewed_at.is_(None),
    )) or 0)
    evidence_gaps = int(await db.scalar(select(func.count(EvidenceGap.id)).where(
        EvidenceGap.matter_id == matter_id,
        EvidenceGap.status == GapStatus.OPEN,
    )) or 0)

    inputs = MatterHealthInput(
        overdue_tasks=overdue_tasks,
        high_priority_tasks=high_tasks,
        deadlines_due_7d=deadlines,
        open_contradictions=contradictions,
        open_high_draft_findings=high_findings,
        unreviewed_court_changes=court_changes,
        open_evidence_gaps=evidence_gaps,
    )
    score, reasons = matter_health_score(inputs, weights)
    return {
        "matter_id": matter_id,
        "score": score,
        "risk_level": classify_health(score).value,
        "overdue_tasks": overdue_tasks,
        "high_priority_tasks": high_tasks,
        "deadlines_due_7d": deadlines,
        "open_contradictions": contradictions,
        "open_high_draft_findings": high_findings,
        "unreviewed_court_changes": court_changes,
        "open_evidence_gaps": evidence_gaps,
        "reasons": reasons,
    }


async def matter_health(db: AsyncSession, actor: ActorContext, *, include_closed: bool = False) -> list[dict]:
    prefs = await get_preferences(db, actor)
    visible = await visible_matter_ids(db, actor)
    if not visible:
        return []
    stmt = select(Matter).where(Matter.id.in_(visible))
    if not include_closed:
        stmt = stmt.where(Matter.status == MatterStatus.ACTIVE)
    matters = list((await db.scalars(stmt.order_by(Matter.updated_at.desc()))).all())
    rows: list[dict] = []
    for matter in matters:
        item = await _matter_health(db, matter.id, prefs.health_weights_json or DEFAULT_HEALTH_WEIGHTS)
        item.update({"title": matter.title, "reference_number": matter.reference_number, "client_name": matter.client_name})
        rows.append(item)
    rows.sort(key=lambda item: (item["score"], item["title"].casefold()))
    return rows


async def _team_rows(db: AsyncSession, actor: ActorContext) -> list[dict]:
    _require(actor, MANAGER_ROLES)
    visible = await visible_matter_ids(db, actor)
    prefs = await get_preferences(db, actor)
    window_start = _today() - timedelta(days=max(1, prefs.rolling_window_days))
    now = utcnow()
    memberships = list((await db.scalars(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == actor.organization_id
    ))).all())
    result: list[dict] = []
    for membership in memberships:
        user = await db.get(SecurityUser, membership.user_id)
        task_base = [WorkflowTask.organization_id == actor.organization_id, WorkflowTask.assigned_membership_id == membership.id]
        if visible:
            task_base.append(or_(WorkflowTask.matter_id.is_(None), WorkflowTask.matter_id.in_(visible)))
        else:
            task_base.append(WorkflowTask.matter_id.is_(None))
        open_tasks = int(await db.scalar(select(func.count(WorkflowTask.id)).where(*task_base, WorkflowTask.status.in_([WorkflowTaskStatus.TODO, WorkflowTaskStatus.IN_PROGRESS]))) or 0)
        overdue = int(await db.scalar(select(func.count(WorkflowTask.id)).where(*task_base, WorkflowTask.status.in_([WorkflowTaskStatus.TODO, WorkflowTaskStatus.IN_PROGRESS]), WorkflowTask.due_at.is_not(None), WorkflowTask.due_at < now)) or 0)
        high = int(await db.scalar(select(func.count(WorkflowTask.id)).where(*task_base, WorkflowTask.status.in_([WorkflowTaskStatus.TODO, WorkflowTaskStatus.IN_PROGRESS]), WorkflowTask.priority.in_([WorkflowTaskPriority.HIGH, WorkflowTaskPriority.URGENT]))) or 0)
        completed = int(await db.scalar(select(func.count(WorkflowTask.id)).where(*task_base, WorkflowTask.status == WorkflowTaskStatus.DONE, WorkflowTask.completed_at.is_not(None), WorkflowTask.completed_at >= datetime.combine(window_start, datetime.min.time(), tzinfo=timezone.utc))) or 0)
        time_filters = [TimeEntry.organization_id == actor.organization_id, TimeEntry.user_id == membership.user_id, TimeEntry.work_date >= window_start]
        if visible:
            time_filters.append(or_(TimeEntry.matter_id.is_(None), TimeEntry.matter_id.in_(visible)))
        else:
            time_filters.append(TimeEntry.matter_id.is_(None))
        billable_minutes = int(await db.scalar(select(func.coalesce(func.sum(TimeEntry.minutes), 0)).where(*time_filters, TimeEntry.billable.is_(True))) or 0)
        submitted_minutes = int(await db.scalar(select(func.coalesce(func.sum(TimeEntry.minutes), 0)).where(*time_filters, TimeEntry.status.in_([TimeEntryStatus.SUBMITTED, TimeEntryStatus.APPROVED, TimeEntryStatus.INVOICED]))) or 0)
        score = workload_score(open_tasks=open_tasks, overdue_tasks=overdue, high_priority_tasks=high)
        result.append({
            "membership_id": membership.id,
            "user_id": membership.user_id,
            "name": user.display_name if user else str(membership.user_id),
            "role": membership.role.value,
            "open_tasks": open_tasks,
            "overdue_tasks": overdue,
            "high_priority_tasks": high,
            "completed_tasks_window": completed,
            "billable_minutes_window": billable_minutes,
            "submitted_minutes_window": submitted_minutes,
            "workload_score": score,
        })
    result.sort(key=lambda row: (-row["workload_score"], row["name"].casefold()))
    return result


async def team_performance(db: AsyncSession, actor: ActorContext) -> list[dict]:
    return await _team_rows(db, actor)


async def financial_summary(db: AsyncSession, actor: ActorContext) -> dict:
    _require(actor, FINANCE_ROLES, "Billing/partner permission is required for financial analytics")
    prefs = await get_preferences(db, actor)
    if actor.role == OrganizationRole.PARTNER and not prefs.show_financials_to_partners:
        raise HTTPException(403, "Organization analytics policy hides financials from partners")
    visible_clients = await _visible_finance_client_ids(db, actor)
    visible_matters = await visible_matter_ids(db, actor)
    today = _today()
    window_start = today - timedelta(days=max(1, prefs.rolling_window_days))

    if not visible_clients:
        return {"currency": prefs.currency, "outstanding_amount": 0.0, "overdue_amount": 0.0, "issued_window": 0.0, "collected_window": 0.0, "collection_rate": 0.0, "ageing": {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}}

    invoice_filters = [
        Invoice.organization_id == actor.organization_id,
        Invoice.client_id.in_(visible_clients),
        Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID]),
    ]
    if actor.role != OrganizationRole.BILLING:
        invoice_filters.append(or_(Invoice.matter_id.is_(None), Invoice.matter_id.in_(visible_matters) if visible_matters else Invoice.matter_id.is_(None)))
    invoices = list((await db.scalars(select(Invoice).where(*invoice_filters))).all())
    outstanding = Decimal("0")
    overdue = Decimal("0")
    issued_window = Decimal("0")
    ageing = {"current": Decimal("0"), "1_30": Decimal("0"), "31_60": Decimal("0"), "61_90": Decimal("0"), "90_plus": Decimal("0")}
    for invoice in invoices:
        due = Decimal(invoice.amount_due or 0)
        if invoice.issue_date and invoice.issue_date >= window_start:
            issued_window += Decimal(invoice.grand_total or 0)
        if due <= 0:
            continue
        outstanding += due
        days_overdue = (today - invoice.due_date).days if invoice.due_date else 0
        if invoice.due_date and invoice.due_date < today:
            overdue += due
        from app.services.analytics.calculator import collection_age_bucket
        ageing[collection_age_bucket(days_overdue)] += due

    payment_filters = [
        Payment.organization_id == actor.organization_id,
        Payment.client_id.in_(visible_clients),
        Payment.status == PaymentStatus.CLEARED,
        Payment.payment_date >= window_start,
    ]
    if actor.role != OrganizationRole.BILLING:
        payment_filters.append(or_(
            Payment.invoice_id.is_(None),
            Invoice.matter_id.is_(None),
            Invoice.matter_id.in_(visible_matters) if visible_matters else False,
        ))
    payment_stmt = select(func.coalesce(func.sum(Payment.amount), 0)).outerjoin(Invoice, Invoice.id == Payment.invoice_id).where(*payment_filters)
    collected = Decimal(await db.scalar(payment_stmt) or 0)
    return {
        "currency": prefs.currency,
        "window_days": prefs.rolling_window_days,
        "outstanding_amount": float(outstanding),
        "overdue_amount": float(overdue),
        "issued_window": float(issued_window),
        "collected_window": float(collected),
        "collection_rate": percentage(collected, issued_window),
        "ageing": {key: float(value) for key, value in ageing.items()},
    }


async def quality_summary(db: AsyncSession, actor: ActorContext) -> dict:
    visible = await visible_matter_ids(db, actor)
    if not visible:
        return {"draft_health_avg": 0.0, "approved_drafts_window": 0, "open_high_draft_findings": 0, "contract_health_avg": 0.0, "open_high_contract_risks": 0, "approved_knowledge_assets": 0, "knowledge_reuse": 0}
    prefs = await get_preferences(db, actor)
    cutoff = utcnow() - timedelta(days=max(1, prefs.rolling_window_days))
    draft_health = float(await db.scalar(select(func.coalesce(func.avg(LegalDraft.health_score), 0)).where(LegalDraft.matter_id.in_(visible))) or 0)
    approved_drafts = int(await db.scalar(select(func.count(LegalDraft.id)).where(LegalDraft.matter_id.in_(visible), LegalDraft.status == LegalDraftStatus.APPROVED, LegalDraft.approved_at.is_not(None), LegalDraft.approved_at >= cutoff)) or 0)
    high_draft_findings = int(await db.scalar(select(func.count(LegalDraftFinding.id)).join(LegalDraft, LegalDraft.id == LegalDraftFinding.draft_id).where(LegalDraft.matter_id.in_(visible), LegalDraftFinding.level == DraftFindingLevel.HIGH, LegalDraftFinding.status == DraftFindingStatus.OPEN)) or 0)
    contract_health = float(await db.scalar(select(func.coalesce(func.avg(Contract.health_score), 0)).where(Contract.matter_id.in_(visible))) or 0)
    contract_risks = int(await db.scalar(select(func.count(ContractRisk.id)).join(Contract, Contract.id == ContractRisk.contract_id).where(Contract.matter_id.in_(visible), ContractRisk.level == ContractRiskLevel.HIGH, ContractRisk.status == ContractRiskStatus.OPEN)) or 0)
    approved_assets = int(await db.scalar(select(func.count(KnowledgeAsset.id)).where(KnowledgeAsset.organization_id == actor.organization_id, KnowledgeAsset.status == KnowledgeAssetStatus.APPROVED)) or 0)
    reuse = int(await db.scalar(select(func.coalesce(func.sum(KnowledgeAsset.usage_count), 0)).where(KnowledgeAsset.organization_id == actor.organization_id, KnowledgeAsset.status == KnowledgeAssetStatus.APPROVED)) or 0)
    return {
        "draft_health_avg": round(draft_health, 1),
        "approved_drafts_window": approved_drafts,
        "open_high_draft_findings": high_draft_findings,
        "contract_health_avg": round(contract_health, 1),
        "open_high_contract_risks": contract_risks,
        "approved_knowledge_assets": approved_assets,
        "knowledge_reuse": reuse,
        "window_days": prefs.rolling_window_days,
    }


async def client_health(db: AsyncSession, actor: ActorContext) -> list[dict]:
    _require(actor, FINANCE_ROLES, "Billing/partner permission is required for client financial analytics")
    prefs = await get_preferences(db, actor)
    if actor.role == OrganizationRole.PARTNER and not prefs.show_financials_to_partners:
        raise HTTPException(403, "Organization analytics policy hides financials from partners")
    visible_clients = await _visible_finance_client_ids(db, actor)
    visible_matters = await visible_matter_ids(db, actor)
    if not visible_clients:
        return []
    clients = list((await db.scalars(select(Client).where(Client.id.in_(visible_clients)).order_by(Client.display_name))).all())
    today = _today()
    output: list[dict] = []
    for client in clients:
        invoice_filters = [
            Invoice.organization_id == actor.organization_id,
            Invoice.client_id == client.id,
            Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID]),
        ]
        if actor.role != OrganizationRole.BILLING:
            invoice_filters.append(or_(Invoice.matter_id.is_(None), Invoice.matter_id.in_(visible_matters) if visible_matters else Invoice.matter_id.is_(None)))
        invoices = list((await db.scalars(select(Invoice).where(*invoice_filters))).all())
        outstanding = sum((Decimal(row.amount_due or 0) for row in invoices), Decimal("0"))
        overdue = sum((Decimal(row.amount_due or 0) for row in invoices if row.due_date and row.due_date < today), Decimal("0"))
        if actor.role == OrganizationRole.BILLING:
            matter_count = 0
            requests = 0
            last_comm = None
        else:
            matter_count = int(await db.scalar(select(func.count(Matter.id)).join_from(Matter, MatterClientLink, Matter.id == MatterClientLink.matter_id).where(
                MatterClientLink.client_id == client.id,
                Matter.id.in_(visible_matters) if visible_matters else Matter.id.is_(None),
                Matter.status == MatterStatus.ACTIVE,
            )) or 0)
            request_filters = [ClientPortalRequest.client_id == client.id, ClientPortalRequest.status.in_([PortalRequestStatus.OPEN, PortalRequestStatus.IN_PROGRESS])]
            if visible_matters:
                request_filters.append(or_(ClientPortalRequest.matter_id.is_(None), ClientPortalRequest.matter_id.in_(visible_matters)))
            else:
                request_filters.append(ClientPortalRequest.matter_id.is_(None))
            requests = int(await db.scalar(select(func.count(ClientPortalRequest.id)).where(*request_filters)) or 0)
            last_comm = await db.scalar(select(func.max(ClientCommunication.occurred_at)).where(
                ClientCommunication.client_id == client.id,
                or_(ClientCommunication.matter_id.is_(None), ClientCommunication.matter_id.in_(visible_matters) if visible_matters else ClientCommunication.matter_id.is_(None)),
            ))
        reasons: list[str] = []
        penalty = 0
        if overdue > 0:
            penalty += 20
            reasons.append("Overdue receivables")
        if requests >= 3:
            penalty += 10
            reasons.append("Multiple open portal requests")
        if last_comm and (utcnow() - (last_comm if last_comm.tzinfo else last_comm.replace(tzinfo=timezone.utc))).days > 30:
            penalty += 10
            reasons.append("No recorded communication in 30+ days")
        score = max(0, 100 - penalty)
        output.append({
            "client_id": client.id,
            "client_name": client.display_name,
            "outstanding_amount": float(outstanding),
            "overdue_amount": float(overdue),
            "open_portal_requests": requests,
            "active_matters": matter_count,
            "last_communication_at": last_comm,
            "health_score": score,
            "reasons": reasons,
        })
    output.sort(key=lambda row: (row["health_score"], -row["overdue_amount"], row["client_name"].casefold()))
    return output


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    health = await matter_health(db, actor)
    visible = await visible_matter_ids(db, actor)
    now = utcnow()
    today = now.date()
    week = today + timedelta(days=7)
    open_statuses = [WorkflowTaskStatus.TODO, WorkflowTaskStatus.IN_PROGRESS]
    if visible:
        overdue_tasks = int(await db.scalar(select(func.count(WorkflowTask.id)).where(
            WorkflowTask.organization_id == actor.organization_id,
            WorkflowTask.status.in_(open_statuses),
            WorkflowTask.matter_id.in_(visible),
            WorkflowTask.due_at.is_not(None),
            WorkflowTask.due_at < now,
        )) or 0)
        hearings = int(await db.scalar(select(func.count(Hearing.id)).where(
            Hearing.matter_id.in_(visible), Hearing.status == HearingStatus.SCHEDULED,
            Hearing.scheduled_for >= now, Hearing.scheduled_for <= now + timedelta(days=7),
        )) or 0)
        deadlines = int(await db.scalar(select(func.count(MatterDeadline.id)).where(
            MatterDeadline.matter_id.in_(visible), MatterDeadline.reviewed_by_lawyer.is_(True), MatterDeadline.status != DeadlineStatus.COMPLETED,
            MatterDeadline.due_date >= today, MatterDeadline.due_date <= week,
        )) or 0)
    else:
        overdue_tasks = hearings = deadlines = 0
    quality = await quality_summary(db, actor)
    financials = None
    if actor.role in FINANCE_ROLES:
        try:
            financials = await financial_summary(db, actor)
        except HTTPException:
            financials = None
    avg_health = round(sum(item["score"] for item in health) / len(health), 1) if health else 0.0
    return {
        "active_matters": len(health),
        "matter_health_avg": avg_health,
        "at_risk_matters": sum(1 for item in health if item["score"] < 60),
        "overdue_tasks": overdue_tasks,
        "upcoming_hearings_7d": hearings,
        "deadlines_due_7d": deadlines,
        "quality": quality,
        "financials": financials,
        "formula_note": "All scores are deterministic, configurable signals. They are management aids, not predictions of legal outcomes or lawyer quality.",
    }


async def _metric_map(db: AsyncSession, actor: ActorContext) -> dict[str, float]:
    dash = await dashboard(db, actor)
    quality = dash["quality"]
    values: dict[str, float] = {
        "matter_health_avg": float(dash["matter_health_avg"]),
        "at_risk_matters": float(dash["at_risk_matters"]),
        "overdue_tasks": float(dash["overdue_tasks"]),
        "deadlines_due_7d": float(dash["deadlines_due_7d"]),
        "draft_health_avg": float(quality["draft_health_avg"]),
        "approved_drafts_30d": float(quality["approved_drafts_window"]),
        "knowledge_reuse": float(quality["knowledge_reuse"]),
    }
    if dash["financials"]:
        values.update({
            "outstanding_amount": float(dash["financials"]["outstanding_amount"]),
            "overdue_amount": float(dash["financials"]["overdue_amount"]),
            "collection_rate_30d": float(dash["financials"]["collection_rate"]),
        })
    return values


async def create_snapshot(db: AsyncSession, actor: ActorContext, *, kind: SnapshotKind, notes: str | None = None) -> AnalyticsSnapshot:
    _require(actor, MANAGER_ROLES)
    prefs = await get_preferences(db, actor)
    period_end = _today()
    period_start = period_end - timedelta(days=max(1, prefs.rolling_window_days) - 1)
    health = await matter_health(db, actor)
    team = await _team_rows(db, actor)
    try:
        clients = await client_health(db, actor)
    except HTTPException:
        clients = []
    metric_map = await _metric_map(db, actor)
    payload = {"period_start": period_start.isoformat(), "period_end": period_end.isoformat(), "metrics": metric_map, "matter_health": health, "team": team, "clients": clients}
    row = AnalyticsSnapshot(
        organization_id=actor.organization_id,
        kind=kind,
        period_start=period_start,
        period_end=period_end,
        generated_by_membership_id=actor.membership_id,
        payload_hash=stable_payload_hash(payload),
        summary_json={"metrics": metric_map, "matter_count": len(health), "member_count": len(team), "client_count": len(clients)},
        notes=notes,
    )
    db.add(row)
    await db.flush()
    for key, value in metric_map.items():
        unit = "currency" if "amount" in key else "percent" if "rate" in key else "score" if "health" in key else "count"
        db.add(AnalyticsMetricValue(snapshot_id=row.id, metric_key=key, scope_type=AnalyticsScope.ORGANIZATION, scope_id=None, numeric_value=value, unit=unit))
    for item in health:
        db.add(MatterHealthSnapshot(
            snapshot_id=row.id, matter_id=item["matter_id"], score=item["score"], risk_level=AnalyticsRiskSeverity(item["risk_level"]),
            overdue_tasks=item["overdue_tasks"], high_priority_tasks=item["high_priority_tasks"], deadlines_due_7d=item["deadlines_due_7d"],
            open_contradictions=item["open_contradictions"], open_high_draft_findings=item["open_high_draft_findings"],
            unreviewed_court_changes=item["unreviewed_court_changes"], open_evidence_gaps=item["open_evidence_gaps"], reasons_json=item["reasons"],
        ))
    for item in team:
        db.add(MemberPerformanceSnapshot(
            snapshot_id=row.id, membership_id=item["membership_id"], open_tasks=item["open_tasks"], overdue_tasks=item["overdue_tasks"],
            high_priority_tasks=item["high_priority_tasks"], completed_tasks_window=item["completed_tasks_window"], billable_minutes_window=item["billable_minutes_window"],
            submitted_minutes_window=item["submitted_minutes_window"], workload_score=item["workload_score"], metadata_json={"name": item["name"], "role": item["role"]},
        ))
    for item in clients:
        db.add(ClientHealthSnapshot(
            snapshot_id=row.id, client_id=item["client_id"], outstanding_amount=item["outstanding_amount"], overdue_amount=item["overdue_amount"],
            open_portal_requests=item["open_portal_requests"], active_matters=item["active_matters"], last_communication_at=item["last_communication_at"],
            health_score=item["health_score"], reasons_json=item["reasons"],
        ))
    await db.commit()
    await db.refresh(row)
    return row


async def list_snapshots(db: AsyncSession, actor: ActorContext, limit: int = 50) -> list[AnalyticsSnapshot]:
    _require(actor, MANAGER_ROLES)
    return list((await db.scalars(select(AnalyticsSnapshot).where(
        AnalyticsSnapshot.organization_id == actor.organization_id
    ).order_by(AnalyticsSnapshot.created_at.desc()).limit(limit))).all())


async def rebuild_risk_signals(db: AsyncSession, actor: ActorContext) -> dict:
    _require(actor, MANAGER_ROLES)
    prefs = await get_preferences(db, actor)
    if not prefs.enable_risk_detection:
        return {"created": 0, "updated": 0, "resolved": 0, "message": "Risk detection is disabled by organization analytics preferences."}
    thresholds = {**DEFAULT_THRESHOLDS, **(prefs.thresholds_json or {})}
    active_keys: set[str] = set()
    created = updated = 0
    now = utcnow()

    async def upsert(*, key: str, signal_type: str, severity: AnalyticsRiskSeverity, title: str, explanation: str, matter_id: UUID | None = None, client_id: UUID | None = None, membership_id: UUID | None = None, metric_key: str | None = None, observed: float | None = None, threshold: float | None = None):
        nonlocal created, updated
        active_keys.add(key)
        row = await db.scalar(select(AnalyticsRiskSignal).where(AnalyticsRiskSignal.organization_id == actor.organization_id, AnalyticsRiskSignal.dedupe_key == key))
        if row:
            row.signal_type = signal_type; row.severity = severity; row.title = title; row.explanation = explanation; row.metric_key = metric_key
            row.observed_value = observed; row.threshold_value = threshold; row.detected_at = now
            if row.status in {AnalyticsRiskStatus.RESOLVED, AnalyticsRiskStatus.DISMISSED}:
                row.status = AnalyticsRiskStatus.OPEN; row.resolved_at = None
            updated += 1
            return
        db.add(AnalyticsRiskSignal(
            organization_id=actor.organization_id, matter_id=matter_id, client_id=client_id, membership_id=membership_id,
            signal_type=signal_type, severity=severity, status=AnalyticsRiskStatus.OPEN, title=title, explanation=explanation,
            metric_key=metric_key, observed_value=observed, threshold_value=threshold, dedupe_key=key, detected_at=now,
        )); created += 1

    for item in await matter_health(db, actor):
        if item["score"] < float(thresholds["matter_health_high_risk"]):
            severity = AnalyticsRiskSeverity.CRITICAL if item["score"] < float(thresholds["matter_health_critical"]) else AnalyticsRiskSeverity.HIGH
            await upsert(
                key=f"matter-health:{item['matter_id']}", signal_type="matter_health", severity=severity,
                title=f"Matter health needs attention: {item['title']}",
                explanation="Deterministic health score crossed the configured risk threshold. Review the listed penalties before taking action.",
                matter_id=item["matter_id"], metric_key="matter_health", observed=float(item["score"]), threshold=float(thresholds["matter_health_high_risk"]),
            )
    for member in await _team_rows(db, actor):
        if member["workload_score"] >= float(thresholds["member_workload_high"]):
            await upsert(
                key=f"member-workload:{member['membership_id']}", signal_type="member_workload", severity=AnalyticsRiskSeverity.HIGH,
                title=f"High operational load: {member['name']}",
                explanation="Open, high-priority and overdue tasks produced a workload score above the configured threshold. This is a workload signal, not a performance rating.",
                membership_id=member["membership_id"], metric_key="member_workload", observed=float(member["workload_score"]), threshold=float(thresholds["member_workload_high"]),
            )
    if actor.role in FINANCE_ROLES:
        try:
            for client in await client_health(db, actor):
                if client["overdue_amount"] >= float(thresholds["client_overdue_amount_high"]):
                    await upsert(
                        key=f"client-overdue:{client['client_id']}", signal_type="client_overdue", severity=AnalyticsRiskSeverity.HIGH,
                        title=f"Material overdue receivable: {client['client_name']}",
                        explanation="Overdue receivables crossed the configured analytics threshold. Confirm invoice/payment records before collection action.",
                        client_id=client["client_id"], metric_key="client_overdue_amount", observed=float(client["overdue_amount"]), threshold=float(thresholds["client_overdue_amount_high"]),
                    )
        except HTTPException:
            pass

    existing = list((await db.scalars(select(AnalyticsRiskSignal).where(
        AnalyticsRiskSignal.organization_id == actor.organization_id,
        AnalyticsRiskSignal.status.in_([AnalyticsRiskStatus.OPEN, AnalyticsRiskStatus.ACKNOWLEDGED]),
    ))).all())
    resolved = 0
    for row in existing:
        if row.dedupe_key not in active_keys and row.signal_type in {"matter_health", "member_workload", "client_overdue"}:
            row.status = AnalyticsRiskStatus.RESOLVED
            row.resolved_at = now
            row.metadata_json = {**(row.metadata_json or {}), "auto_resolved": True}
            resolved += 1
    await db.commit()
    return {"created": created, "updated": updated, "resolved": resolved, "active": len(active_keys)}


async def list_risk_signals(db: AsyncSession, actor: ActorContext, *, status: AnalyticsRiskStatus | None = None, limit: int = 200) -> list[AnalyticsRiskSignal]:
    _require(actor, MANAGER_ROLES)
    visible_matters = await visible_matter_ids(db, actor)
    visible_clients = await visible_client_ids(db, actor)
    stmt = select(AnalyticsRiskSignal).where(AnalyticsRiskSignal.organization_id == actor.organization_id)
    # Organization/member signals are visible; matter/client signals must independently satisfy confidentiality.
    stmt = stmt.where(or_(
        and_(AnalyticsRiskSignal.matter_id.is_(None), AnalyticsRiskSignal.client_id.is_(None)),
        AnalyticsRiskSignal.matter_id.in_(visible_matters) if visible_matters else False,
        AnalyticsRiskSignal.client_id.in_(visible_clients) if visible_clients else False,
    ))
    if status:
        stmt = stmt.where(AnalyticsRiskSignal.status == status)
    return list((await db.scalars(stmt.order_by(AnalyticsRiskSignal.detected_at.desc()).limit(limit))).all())


async def update_risk_signal(db: AsyncSession, actor: ActorContext, signal_id: UUID, status: AnalyticsRiskStatus) -> AnalyticsRiskSignal:
    _require(actor, MANAGER_ROLES)
    row = await db.get(AnalyticsRiskSignal, signal_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Analytics risk signal not found")
    visible_m = await visible_matter_ids(db, actor)
    visible_c = await visible_client_ids(db, actor)
    if row.matter_id and row.matter_id not in visible_m:
        raise HTTPException(403, "Matter access is required")
    if row.client_id and row.client_id not in visible_c:
        raise HTTPException(403, "Client access is required")
    row.status = status
    row.reviewed_by_user_id = actor.user_id
    if status == AnalyticsRiskStatus.ACKNOWLEDGED:
        row.acknowledged_at = utcnow()
    if status in {AnalyticsRiskStatus.RESOLVED, AnalyticsRiskStatus.DISMISSED}:
        row.resolved_at = utcnow()
    await db.commit(); await db.refresh(row); return row


async def create_goal(db: AsyncSession, actor: ActorContext, values: dict) -> AnalyticsGoal:
    _require(actor, MANAGER_ROLES)
    if values.get("scope_type", AnalyticsScope.ORGANIZATION) != AnalyticsScope.ORGANIZATION:
        raise HTTPException(422, "Batch 17 goal tracking currently supports organization-scope metrics only")
    metric_values = await _metric_map(db, actor)
    if values.get("metric_key") not in metric_values:
        raise HTTPException(422, f"Metric {values.get('metric_key')!r} is not available to this role")
    row = AnalyticsGoal(organization_id=actor.organization_id, created_by_membership_id=actor.membership_id, **values)
    db.add(row); await db.commit(); await db.refresh(row)
    await record_goal_progress(db, actor, row)
    return row


async def list_goals(db: AsyncSession, actor: ActorContext) -> list[dict]:
    _require(actor, MANAGER_ROLES)
    rows = list((await db.scalars(select(AnalyticsGoal).where(AnalyticsGoal.organization_id == actor.organization_id).order_by(AnalyticsGoal.end_date, AnalyticsGoal.created_at))).all())
    output = []
    for row in rows:
        progress = await db.scalar(select(AnalyticsGoalProgress).where(AnalyticsGoalProgress.goal_id == row.id).order_by(AnalyticsGoalProgress.recorded_at.desc()))
        output.append({"goal": row, "progress": progress})
    return output


async def record_goal_progress(db: AsyncSession, actor: ActorContext, goal: AnalyticsGoal) -> AnalyticsGoalProgress:
    metric_values = await _metric_map(db, actor)
    if goal.scope_type != AnalyticsScope.ORGANIZATION:
        raise HTTPException(422, "Batch 17 goal tracking currently supports organization-scope metrics only")
    if goal.metric_key not in metric_values:
        raise HTTPException(422, f"Metric {goal.metric_key!r} is not available to this role")
    actual = float(metric_values[goal.metric_key])
    pct, met = goal_progress(actual, goal.target_value, goal.comparison)
    row = AnalyticsGoalProgress(goal_id=goal.id, recorded_at=utcnow(), actual_value=actual, target_value=goal.target_value, progress_percent=pct, target_met=met)
    db.add(row)
    if met and goal.status == AnalyticsGoalStatus.ACTIVE:
        goal.status = AnalyticsGoalStatus.COMPLETED
    await db.commit(); await db.refresh(row); return row
