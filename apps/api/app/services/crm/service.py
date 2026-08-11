from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import (
    Client, ClientAccessGrant, ClientCommunication, ClientContact, ClientKYCRecord, ClientNote, ClientOnboarding, ClientSecurityProfile,
    ClientPortalAccess, ClientStatus, ConflictCandidate, ConflictCandidateType, ConflictCheck,
    ConflictCheckStatus, CRMLead, CRMTask, CRMTaskStatus, Engagement, EngagementStatus, KYCStatus,
    LeadStatus, MatterClientLink, OnboardingStatus, PortalAccessStatus, TimeEntry,
)
from app.models.matter import Matter, MatterLanguage
from app.models.security import (
    AccessEffect, AuditOutcome, MatterAccessGrant, MatterAccessLevel, MatterSecurityProfile,
    OrganizationMembership, OrganizationRole,
)
from app.schemas.crm import (
    ClientCreate, ClientUpdate, CommunicationCreate, ConflictCheckCreate, ContactCreate,
    EngagementCreate, KYCRecordCreate, LeadCreate, LeadUpdate, MatterOpenRequest, NoteCreate,
    PortalInviteCreate, TaskCreate, TaskUpdate, TimeEntryCreate,
)
from app.services.crm.conflicts import CandidateInput, onboarding_readiness, score_candidate
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext
from app.services.security.permissions import decide_client_access, decide_matter_access, visible_client_ids, visible_matter_ids

CRM_WRITE_ROLES = {
    OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER,
    OrganizationRole.LAWYER, OrganizationRole.JUNIOR, OrganizationRole.PARALEGAL,
}
CRM_MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER, OrganizationRole.LAWYER}
BILLING_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER, OrganizationRole.LAWYER, OrganizationRole.BILLING}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_role(actor: ActorContext, allowed: set[OrganizationRole]) -> None:
    if actor.role not in allowed:
        raise HTTPException(status_code=403, detail="Your role does not permit this CRM action")


async def _audit(db: AsyncSession, actor: ActorContext, action: str, resource_type: str, resource_id: UUID | str, metadata: dict | None = None) -> None:
    await append_audit_event(
        db, organization_id=actor.organization_id, actor=actor, action=action,
        resource_type=resource_type, resource_id=str(resource_id), outcome=AuditOutcome.SUCCESS,
        metadata=metadata or {},
    )


async def list_leads(db: AsyncSession, actor: ActorContext, limit: int = 100) -> list[CRMLead]:
    return list((await db.scalars(select(CRMLead).where(CRMLead.organization_id == actor.organization_id).order_by(CRMLead.updated_at.desc()).limit(limit))).all())


async def create_lead(db: AsyncSession, actor: ActorContext, payload: LeadCreate) -> CRMLead:
    _require_role(actor, CRM_WRITE_ROLES)
    lead = CRMLead(organization_id=actor.organization_id, created_by_user_id=actor.user_id, **payload.model_dump())
    db.add(lead); await db.flush()
    await _audit(db, actor, "crm.lead.create", "crm_lead", lead.id)
    await db.commit(); await db.refresh(lead)
    return lead


async def update_lead(db: AsyncSession, actor: ActorContext, lead_id: UUID, payload: LeadUpdate) -> CRMLead:
    _require_role(actor, CRM_WRITE_ROLES)
    lead = await db.get(CRMLead, lead_id)
    if not lead or lead.organization_id != actor.organization_id:
        raise HTTPException(404, "Lead not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(lead, key, value)
    await _audit(db, actor, "crm.lead.update", "crm_lead", lead.id, {"fields": list(payload.model_dump(exclude_unset=True))})
    await db.commit(); await db.refresh(lead)
    return lead


async def _next_client_number(db: AsyncSession, organization_id: UUID) -> str:
    count = await db.scalar(select(func.count(Client.id)).where(Client.organization_id == organization_id)) or 0
    # Human-friendly reference only; UUID remains authoritative. Unique constraint protects races.
    return f"CL-{_now().year}-{count + 1:05d}"


async def list_clients(db: AsyncSession, actor: ActorContext, limit: int = 100) -> list[Client]:
    visible = await visible_client_ids(db, actor)
    if not visible:
        return []
    return list((await db.scalars(select(Client).where(Client.id.in_(visible)).order_by(Client.updated_at.desc()).limit(limit))).all())


async def get_client(db: AsyncSession, actor: ActorContext, client_id: UUID) -> Client:
    client = await db.get(Client, client_id)
    if not client or client.organization_id != actor.organization_id:
        raise HTTPException(404, "Client not found")
    decision = await decide_client_access(db, actor, client_id, required=MatterAccessLevel.VIEW)
    if not decision.allowed:
        raise HTTPException(403, decision.reason)
    return client


async def create_client(db: AsyncSession, actor: ActorContext, payload: ClientCreate) -> Client:
    _require_role(actor, CRM_WRITE_ROLES)
    client = Client(
        organization_id=actor.organization_id, client_number=await _next_client_number(db, actor.organization_id),
        created_by_user_id=actor.user_id, **payload.model_dump(),
    )
    db.add(client); await db.flush()
    db.add(ClientSecurityProfile(client_id=client.id, created_by_user_id=actor.user_id))
    db.add(ClientOnboarding(organization_id=actor.organization_id, client_id=client.id, status=OnboardingStatus.NOT_STARTED))
    await _audit(db, actor, "crm.client.create", "client", client.id)
    await db.commit(); await db.refresh(client)
    return client


async def update_client(db: AsyncSession, actor: ActorContext, client_id: UUID, payload: ClientUpdate) -> Client:
    _require_role(actor, CRM_WRITE_ROLES)
    client = await get_client(db, actor, client_id)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(client, key, value)
    await _audit(db, actor, "crm.client.update", "client", client.id, {"fields": list(payload.model_dump(exclude_unset=True))})
    await db.commit(); await db.refresh(client)
    return client


async def convert_lead(db: AsyncSession, actor: ActorContext, lead_id: UUID, *, client_type, legal_name: str | None) -> Client:
    _require_role(actor, CRM_WRITE_ROLES)
    lead = await db.get(CRMLead, lead_id)
    if not lead or lead.organization_id != actor.organization_id: raise HTTPException(404, "Lead not found")
    if lead.status == LeadStatus.CONVERTED: raise HTTPException(409, "Lead is already converted")
    client = Client(
        organization_id=actor.organization_id, client_number=await _next_client_number(db, actor.organization_id),
        client_type=client_type, status=ClientStatus.PROSPECT, display_name=lead.name,
        legal_name=legal_name or lead.company_name or lead.name, email=lead.email, phone=lead.phone,
        preferred_language=lead.language, source_lead_id=lead.id, created_by_user_id=actor.user_id,
    )
    db.add(client); await db.flush()
    db.add(ClientSecurityProfile(client_id=client.id, created_by_user_id=actor.user_id))
    latest_check = await db.scalar(
        select(ConflictCheck).where(ConflictCheck.lead_id == lead.id).order_by(ConflictCheck.created_at.desc()).limit(1)
    )
    conflict_cleared = bool(latest_check and latest_check.status in {ConflictCheckStatus.CLEARED, ConflictCheckStatus.OVERRIDDEN})
    db.add(ClientOnboarding(
        organization_id=actor.organization_id, client_id=client.id, status=OnboardingStatus.IN_PROGRESS,
        conflict_check_id=latest_check.id if latest_check else None, conflict_cleared=conflict_cleared,
    ))
    if latest_check and latest_check.client_id is None:
        latest_check.client_id = client.id
    lead.status = LeadStatus.CONVERTED
    await _audit(db, actor, "crm.lead.convert", "client", client.id, {"lead_id": str(lead.id)})
    await db.commit(); await db.refresh(client)
    return client


async def run_conflict_check(db: AsyncSession, actor: ActorContext, payload: ConflictCheckCreate) -> tuple[ConflictCheck, list[ConflictCandidate]]:
    _require_role(actor, CRM_MANAGER_ROLES)
    check = ConflictCheck(
        organization_id=actor.organization_id, lead_id=payload.lead_id, client_id=payload.client_id,
        requested_by_user_id=actor.user_id, subject_name=payload.subject_name.strip(),
        related_parties_json=[p.strip() for p in payload.related_parties if p.strip()],
        status=ConflictCheckStatus.PENDING,
    )
    db.add(check); await db.flush()

    source_email = source_phone = None
    if payload.lead_id:
        lead = await db.get(CRMLead, payload.lead_id)
        if not lead or lead.organization_id != actor.organization_id:
            raise HTTPException(404, "Lead not found")
        source_email, source_phone = lead.email, lead.phone
        if lead.status not in {LeadStatus.CONVERTED, LeadStatus.LOST}:
            lead.status = LeadStatus.CONFLICT_CHECK
    elif payload.client_id:
        client = await db.get(Client, payload.client_id)
        if not client or client.organization_id != actor.organization_id:
            raise HTTPException(404, "Client not found")
        source_email, source_phone = client.email, client.phone

    inputs: list[CandidateInput] = []
    visible_clients = await visible_client_ids(db, actor)
    for row in (await db.scalars(select(Client).where(Client.organization_id == actor.organization_id))).all():
        if payload.client_id and row.id == payload.client_id: continue
        inputs.append(CandidateInput(
            "client", row.id, row.display_name, row.email, row.phone,
            restricted=row.id not in visible_clients, metadata={"client_number": row.client_number},
        ))
    for row in (await db.scalars(select(ClientContact).where(ClientContact.organization_id == actor.organization_id))).all():
        inputs.append(CandidateInput(
            "contact", row.id, row.name, row.email, row.phone, restricted=row.client_id not in visible_clients,
            metadata={"client_id": str(row.client_id)},
        ))

    visible = await visible_matter_ids(db, actor)
    for row in (await db.scalars(select(Matter).where(Matter.organization_id == actor.organization_id))).all():
        restricted = row.id not in visible
        name = row.title if not restricted else row.title  # score internally; never expose if restricted.
        inputs.append(CandidateInput("matter", row.id, name, restricted=restricted, metadata={"reference_number": row.reference_number}))

    candidates: list[ConflictCandidate] = []
    for item in inputs:
        hit = score_candidate(check.subject_name, check.related_parties_json, email=source_email, phone=source_phone, candidate=item)
        if not hit: continue
        score, reason = hit
        public_name = "Restricted relationship — security review required" if item.restricted else item.name
        public_id = None if item.restricted else item.candidate_id
        row = ConflictCandidate(
            conflict_check_id=check.id, candidate_type=ConflictCandidateType(item.candidate_type),
            candidate_id=public_id, candidate_name=public_name, reason=reason, match_score=score,
            metadata_json={} if item.restricted else (item.metadata or {}),
        )
        db.add(row); candidates.append(row)
    check.status = ConflictCheckStatus.REVIEW_REQUIRED if candidates else ConflictCheckStatus.PENDING
    check.search_snapshot_json = {"candidate_count": len(candidates), "algorithm": "deterministic-v1", "threshold": 0.86}
    await _audit(db, actor, "crm.conflict.run", "conflict_check", check.id, {"candidate_count": len(candidates)})
    await db.commit(); await db.refresh(check)
    for candidate in candidates: await db.refresh(candidate)
    return check, candidates


async def review_conflict_check(db: AsyncSession, actor: ActorContext, check_id: UUID, *, decision: ConflictCheckStatus, note: str) -> ConflictCheck:
    _require_role(actor, CRM_MANAGER_ROLES)
    check = await db.get(ConflictCheck, check_id)
    if not check or check.organization_id != actor.organization_id: raise HTTPException(404, "Conflict check not found")
    check.status = decision; check.review_note = note; check.reviewed_by_user_id = actor.user_id; check.reviewed_at = _now()
    if check.lead_id:
        lead = await db.get(CRMLead, check.lead_id)
        if lead and lead.status not in {LeadStatus.CONVERTED, LeadStatus.LOST}:
            lead.status = LeadStatus.ONBOARDING if decision in {ConflictCheckStatus.CLEARED, ConflictCheckStatus.OVERRIDDEN} else LeadStatus.CONFLICT_CHECK
    if check.client_id:
        onboarding = await db.scalar(select(ClientOnboarding).where(ClientOnboarding.client_id == check.client_id))
        if onboarding:
            onboarding.conflict_check_id = check.id
            onboarding.conflict_cleared = decision in {ConflictCheckStatus.CLEARED, ConflictCheckStatus.OVERRIDDEN}
            await refresh_onboarding_status(onboarding)
    await _audit(db, actor, "crm.conflict.review", "conflict_check", check.id, {"decision": decision.value})
    await db.commit(); await db.refresh(check)
    return check


async def list_conflict_checks(db: AsyncSession, actor: ActorContext, limit: int = 100) -> list[tuple[ConflictCheck, list[ConflictCandidate]]]:
    checks = list((await db.scalars(select(ConflictCheck).where(ConflictCheck.organization_id == actor.organization_id).order_by(ConflictCheck.created_at.desc()).limit(limit))).all())
    output = []
    for check in checks:
        candidates = list((await db.scalars(select(ConflictCandidate).where(ConflictCandidate.conflict_check_id == check.id).order_by(ConflictCandidate.match_score.desc()))).all())
        output.append((check, candidates))
    return output


async def refresh_onboarding_status(onboarding: ClientOnboarding) -> None:
    state, _ = onboarding_readiness(
        conflict_cleared=onboarding.conflict_cleared, identity_complete=onboarding.identity_complete,
        address_complete=onboarding.address_complete, engagement_complete=onboarding.engagement_complete,
    )
    onboarding.status = OnboardingStatus.READY if state == "ready" else OnboardingStatus.IN_PROGRESS
    if state == "ready" and onboarding.completed_at is None:
        # READY means all machine-checkable gates complete; COMPLETE remains an explicit lawyer action.
        pass


async def get_onboarding(db: AsyncSession, actor: ActorContext, client_id: UUID) -> ClientOnboarding:
    await get_client(db, actor, client_id)
    row = await db.scalar(select(ClientOnboarding).where(ClientOnboarding.client_id == client_id))
    if row is None:
        row = ClientOnboarding(organization_id=actor.organization_id, client_id=client_id)
        db.add(row); await db.commit(); await db.refresh(row)
    return row


async def create_kyc(db: AsyncSession, actor: ActorContext, client_id: UUID, payload: KYCRecordCreate) -> ClientKYCRecord:
    _require_role(actor, CRM_MANAGER_ROLES)
    await get_client(db, actor, client_id)
    record = ClientKYCRecord(organization_id=actor.organization_id, client_id=client_id, **payload.model_dump())
    db.add(record); await db.flush(); await _audit(db, actor, "crm.kyc.create", "kyc_record", record.id, {"document_type": record.document_type})
    await db.commit(); await db.refresh(record); return record


async def verify_kyc(db: AsyncSession, actor: ActorContext, record_id: UUID, kyc_status: KYCStatus, notes: str | None) -> ClientKYCRecord:
    _require_role(actor, CRM_MANAGER_ROLES)
    row = await db.get(ClientKYCRecord, record_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "KYC record not found")
    row.status = kyc_status; row.notes = notes if notes is not None else row.notes
    if kyc_status == KYCStatus.VERIFIED:
        row.verified_by_user_id = actor.user_id; row.verified_at = _now()
    onboarding = await get_onboarding(db, actor, row.client_id)
    verified = await db.scalar(select(func.count(ClientKYCRecord.id)).where(ClientKYCRecord.client_id == row.client_id, ClientKYCRecord.status == KYCStatus.VERIFIED)) or 0
    onboarding.identity_complete = verified > 0
    await refresh_onboarding_status(onboarding)
    await _audit(db, actor, "crm.kyc.review", "kyc_record", row.id, {"status": kyc_status.value})
    await db.commit(); await db.refresh(row); return row


async def add_contact(db: AsyncSession, actor: ActorContext, client_id: UUID, payload: ContactCreate) -> ClientContact:
    _require_role(actor, CRM_WRITE_ROLES); await get_client(db, actor, client_id)
    row = ClientContact(organization_id=actor.organization_id, client_id=client_id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def create_engagement(db: AsyncSession, actor: ActorContext, client_id: UUID, payload: EngagementCreate) -> Engagement:
    _require_role(actor, CRM_MANAGER_ROLES); await get_client(db, actor, client_id)
    if payload.matter_id:
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.MANAGE)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    row = Engagement(organization_id=actor.organization_id, client_id=client_id, **payload.model_dump())
    db.add(row); await db.flush()
    if row.status == EngagementStatus.ACTIVE:
        onboarding = await get_onboarding(db, actor, client_id); onboarding.engagement_complete = True; await refresh_onboarding_status(onboarding)
    await _audit(db, actor, "crm.engagement.create", "engagement", row.id)
    await db.commit(); await db.refresh(row); return row


async def open_matter(db: AsyncSession, actor: ActorContext, client_id: UUID, payload: MatterOpenRequest) -> Matter:
    _require_role(actor, CRM_MANAGER_ROLES)
    client = await get_client(db, actor, client_id)
    onboarding = await get_onboarding(db, actor, client_id)
    if not onboarding.conflict_cleared:
        raise HTTPException(409, "A cleared or expressly overridden conflict check is required before opening a matter")
    lang_map = {"en": MatterLanguage.ENGLISH, "hi": MatterLanguage.HINDI, "bilingual": MatterLanguage.BILINGUAL}
    matter = Matter(
        organization_id=actor.organization_id, created_by_user_id=actor.user_id,
        title=payload.title, client_name=client.display_name, description=payload.description,
        primary_language=lang_map.get(payload.primary_language, MatterLanguage.BILINGUAL),
    )
    db.add(matter); await db.flush()
    db.add(MatterSecurityProfile(matter_id=matter.id, created_by_user_id=actor.user_id))
    db.add(MatterClientLink(organization_id=actor.organization_id, matter_id=matter.id, client_id=client.id, is_primary=True))
    for membership_id in set(payload.team_membership_ids):
        membership = await db.get(OrganizationMembership, membership_id)
        if not membership or membership.organization_id != actor.organization_id:
            raise HTTPException(422, "A selected team member does not belong to this organization")
        db.add(MatterAccessGrant(
            matter_id=matter.id, membership_id=membership_id, effect=AccessEffect.ALLOW,
            access_level=MatterAccessLevel.WORK, granted_by_user_id=actor.user_id, reason="Assigned during client intake",
        ))
    if payload.engagement_id:
        engagement = await db.get(Engagement, payload.engagement_id)
        if not engagement or engagement.client_id != client.id or engagement.organization_id != actor.organization_id:
            raise HTTPException(422, "Engagement does not belong to this client")
        engagement.matter_id = matter.id
    client.status = ClientStatus.ACTIVE
    await _audit(db, actor, "crm.matter.open", "matter", matter.id, {"client_id": str(client.id)})
    await db.commit(); await db.refresh(matter); return matter


async def add_note(db: AsyncSession, actor: ActorContext, client_id: UUID, payload: NoteCreate) -> ClientNote:
    _require_role(actor, CRM_WRITE_ROLES); await get_client(db, actor, client_id)
    if payload.matter_id:
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    row = ClientNote(organization_id=actor.organization_id, client_id=client_id, author_user_id=actor.user_id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def create_task(db: AsyncSession, actor: ActorContext, payload: TaskCreate) -> CRMTask:
    _require_role(actor, CRM_WRITE_ROLES)
    if payload.matter_id:
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    row = CRMTask(organization_id=actor.organization_id, created_by_user_id=actor.user_id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def update_task(db: AsyncSession, actor: ActorContext, task_id: UUID, payload: TaskUpdate) -> CRMTask:
    _require_role(actor, CRM_WRITE_ROLES)
    row = await db.get(CRMTask, task_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Task not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(row, key, value)
    if row.status == CRMTaskStatus.DONE and row.completed_at is None: row.completed_at = _now()
    if row.status != CRMTaskStatus.DONE: row.completed_at = None
    await db.commit(); await db.refresh(row); return row


async def list_tasks(db: AsyncSession, actor: ActorContext, limit: int = 100) -> list[CRMTask]:
    stmt = select(CRMTask).where(CRMTask.organization_id == actor.organization_id).order_by(CRMTask.due_at.asc().nullslast(), CRMTask.created_at.desc()).limit(limit)
    rows = list((await db.scalars(stmt)).all())
    visible = await visible_matter_ids(db, actor)
    return [row for row in rows if row.matter_id is None or row.matter_id in visible]


async def log_communication(db: AsyncSession, actor: ActorContext, client_id: UUID, payload: CommunicationCreate) -> ClientCommunication:
    _require_role(actor, CRM_WRITE_ROLES); await get_client(db, actor, client_id)
    if payload.matter_id:
        decision = await decide_matter_access(db, actor, payload.matter_id)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    row = ClientCommunication(organization_id=actor.organization_id, client_id=client_id, recorded_by_user_id=actor.user_id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def add_time_entry(db: AsyncSession, actor: ActorContext, payload: TimeEntryCreate) -> TimeEntry:
    _require_role(actor, BILLING_ROLES)
    if payload.matter_id:
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed and actor.role != OrganizationRole.BILLING: raise HTTPException(403, decision.reason)
    row = TimeEntry(organization_id=actor.organization_id, user_id=actor.user_id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def invite_portal(db: AsyncSession, actor: ActorContext, client_id: UUID, payload: PortalInviteCreate) -> ClientPortalAccess:
    _require_role(actor, CRM_MANAGER_ROLES); await get_client(db, actor, client_id)
    row = ClientPortalAccess(
        organization_id=actor.organization_id, client_id=client_id, contact_id=payload.contact_id,
        email=payload.email.strip().casefold(), status=PortalAccessStatus.INVITED,
        invited_by_user_id=actor.user_id, invited_at=_now(), permissions_json=payload.permissions,
    )
    db.add(row); await db.flush()
    await _audit(db, actor, "crm.portal.invite", "client_portal_access", row.id, {"client_id": str(client_id)})
    await db.commit(); await db.refresh(row); return row


async def overview(db: AsyncSession, actor: ActorContext) -> dict:
    now = _now()
    leads_open = await db.scalar(select(func.count(CRMLead.id)).where(CRMLead.organization_id == actor.organization_id, CRMLead.status.notin_([LeadStatus.CONVERTED, LeadStatus.LOST]))) or 0
    clients_active = await db.scalar(select(func.count(Client.id)).where(Client.organization_id == actor.organization_id, Client.status == ClientStatus.ACTIVE)) or 0
    conflict_reviews = await db.scalar(select(func.count(ConflictCheck.id)).where(ConflictCheck.organization_id == actor.organization_id, ConflictCheck.status.in_([ConflictCheckStatus.PENDING, ConflictCheckStatus.REVIEW_REQUIRED]))) or 0
    onboarding_open = await db.scalar(select(func.count(ClientOnboarding.id)).where(ClientOnboarding.organization_id == actor.organization_id, ClientOnboarding.status.notin_([OnboardingStatus.COMPLETE]))) or 0
    tasks = await list_tasks(db, actor, 500)
    tasks_due = sum(1 for task in tasks if task.status in {CRMTaskStatus.TODO, CRMTaskStatus.IN_PROGRESS} and task.due_at and task.due_at <= now)
    visible = await visible_matter_ids(db, actor)
    time_stmt = select(func.coalesce(func.sum(TimeEntry.minutes), 0)).where(TimeEntry.organization_id == actor.organization_id, TimeEntry.status != "invoiced")
    if actor.role != OrganizationRole.BILLING:
        time_stmt = time_stmt.where(or_(TimeEntry.matter_id.is_(None), TimeEntry.matter_id.in_(visible))) if visible else time_stmt.where(TimeEntry.matter_id.is_(None))
    unbilled_minutes = int(await db.scalar(time_stmt) or 0)
    return dict(leads_open=leads_open, clients_active=clients_active, conflict_reviews=conflict_reviews, onboarding_open=onboarding_open, tasks_due=tasks_due, unbilled_minutes=unbilled_minutes)

async def update_onboarding(db: AsyncSession, actor: ActorContext, client_id: UUID, *, address_complete: bool | None, engagement_complete: bool | None, notes: str | None, mark_complete: bool) -> ClientOnboarding:
    _require_role(actor, CRM_MANAGER_ROLES)
    row = await get_onboarding(db, actor, client_id)
    if address_complete is not None: row.address_complete = address_complete
    if engagement_complete is not None: row.engagement_complete = engagement_complete
    if notes is not None: row.notes = notes
    await refresh_onboarding_status(row)
    if mark_complete:
        if row.status != OnboardingStatus.READY:
            raise HTTPException(409, "Conflict, identity, address, and engagement gates must be ready before onboarding can be completed")
        row.status = OnboardingStatus.COMPLETE; row.completed_at = _now()
        client = await get_client(db, actor, client_id); client.status = ClientStatus.ACTIVE
    await _audit(db, actor, "crm.onboarding.update", "client_onboarding", row.id, {"status": row.status.value})
    await db.commit(); await db.refresh(row); return row


async def client_detail(db: AsyncSession, actor: ActorContext, client_id: UUID) -> dict:
    client = await get_client(db, actor, client_id)
    onboarding = await get_onboarding(db, actor, client_id)
    contacts = list((await db.scalars(select(ClientContact).where(ClientContact.client_id == client_id).order_by(ClientContact.is_primary.desc(), ClientContact.name))).all())
    kyc = list((await db.scalars(select(ClientKYCRecord).where(ClientKYCRecord.client_id == client_id).order_by(ClientKYCRecord.created_at.desc()))).all())
    visible = await visible_matter_ids(db, actor)
    engagement_stmt = select(Engagement).where(Engagement.client_id == client_id)
    if visible:
        engagement_stmt = engagement_stmt.where(or_(Engagement.matter_id.is_(None), Engagement.matter_id.in_(visible)))
    else:
        engagement_stmt = engagement_stmt.where(Engagement.matter_id.is_(None))
    engagements = list((await db.scalars(engagement_stmt.order_by(Engagement.created_at.desc()))).all())
    links = list((await db.scalars(select(MatterClientLink).where(MatterClientLink.client_id == client_id))).all())
    matters = []
    for link in links:
        if link.matter_id in visible:
            matter = await db.get(Matter, link.matter_id)
            if matter: matters.append({"id": str(matter.id), "title": matter.title, "status": matter.status.value, "reference_number": matter.reference_number})
    note_stmt = select(ClientNote).where(ClientNote.client_id == client_id)
    comm_stmt = select(ClientCommunication).where(ClientCommunication.client_id == client_id)
    if visible:
        note_stmt = note_stmt.where(or_(ClientNote.matter_id.is_(None), ClientNote.matter_id.in_(visible)))
        comm_stmt = comm_stmt.where(or_(ClientCommunication.matter_id.is_(None), ClientCommunication.matter_id.in_(visible)))
    else:
        note_stmt = note_stmt.where(ClientNote.matter_id.is_(None))
        comm_stmt = comm_stmt.where(ClientCommunication.matter_id.is_(None))
    if actor.role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}:
        note_stmt = note_stmt.where(or_(ClientNote.is_private.is_(False), ClientNote.author_user_id == actor.user_id))
    notes = list((await db.scalars(note_stmt.order_by(ClientNote.created_at.desc()).limit(50))).all())
    communications = list((await db.scalars(comm_stmt.order_by(ClientCommunication.occurred_at.desc()).limit(50))).all())
    portals = list((await db.scalars(select(ClientPortalAccess).where(ClientPortalAccess.client_id == client_id).order_by(ClientPortalAccess.created_at.desc()))).all())
    return {"client": client, "onboarding": onboarding, "contacts": contacts, "kyc": kyc, "engagements": engagements, "matters": matters, "notes": notes, "communications": communications, "portal_access": portals}

async def get_client_security(db: AsyncSession, actor: ActorContext, client_id: UUID) -> ClientSecurityProfile:
    _require_role(actor, CRM_MANAGER_ROLES)
    client = await db.get(Client, client_id)
    if not client or client.organization_id != actor.organization_id:
        raise HTTPException(404, "Client not found")
    row = await db.scalar(select(ClientSecurityProfile).where(ClientSecurityProfile.client_id == client_id))
    if row is None:
        row = ClientSecurityProfile(client_id=client_id, created_by_user_id=actor.user_id)
        db.add(row); await db.commit(); await db.refresh(row)
    return row


async def update_client_security(db: AsyncSession, actor: ActorContext, client_id: UUID, *, classification, access_mode, notes: str | None) -> ClientSecurityProfile:
    row = await get_client_security(db, actor, client_id)
    row.classification = classification; row.access_mode = access_mode; row.notes = notes
    await _audit(db, actor, "crm.client_security.update", "client", client_id, {"classification": classification.value, "access_mode": access_mode.value})
    await db.commit(); await db.refresh(row); return row


async def create_client_grant(db: AsyncSession, actor: ActorContext, client_id: UUID, *, membership_id: UUID, effect, access_level, reason: str | None) -> ClientAccessGrant:
    _require_role(actor, CRM_MANAGER_ROLES)
    client = await db.get(Client, client_id)
    if not client or client.organization_id != actor.organization_id:
        raise HTTPException(404, "Client not found")
    membership = await db.get(OrganizationMembership, membership_id)
    if not membership or membership.organization_id != actor.organization_id:
        raise HTTPException(422, "Membership does not belong to this organization")
    row = await db.scalar(select(ClientAccessGrant).where(ClientAccessGrant.client_id == client_id, ClientAccessGrant.membership_id == membership_id))
    if row is None:
        row = ClientAccessGrant(client_id=client_id, membership_id=membership_id, granted_by_user_id=actor.user_id)
        db.add(row)
    row.effect = effect; row.access_level = access_level; row.reason = reason; row.granted_by_user_id = actor.user_id
    await _audit(db, actor, "crm.client_security.grant", "client", client_id, {"membership_id": str(membership_id), "effect": effect.value, "access_level": access_level.value})
    await db.commit(); await db.refresh(row); return row


async def list_client_grants(db: AsyncSession, actor: ActorContext, client_id: UUID) -> list[ClientAccessGrant]:
    await get_client_security(db, actor, client_id)
    return list((await db.scalars(select(ClientAccessGrant).where(ClientAccessGrant.client_id == client_id).order_by(ClientAccessGrant.created_at))).all())
