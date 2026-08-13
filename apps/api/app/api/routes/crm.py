from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.crm import ConflictCandidate
from app.models.matter import Matter
from app.schemas.crm import (
    ClientCommunicationRead, ClientCreate, ClientDetail, ClientGrantCreate, ClientGrantRead, ClientMatterSummary, ClientNoteRead,
    ClientRead, ClientSecurityRead, ClientSecurityUpdate, ClientUpdate, CommunicationCreate, ConflictCandidateRead,
    ConflictCheckCreate, ConflictCheckRead, ConflictDecision, ContactCreate, ContactRead,
    ConvertLeadRequest, CRMOverview, EngagementCreate, EngagementRead, KYCRecordCreate,
    KYCRecordRead, KYCVerifyRequest, LeadCreate, LeadRead, LeadUpdate, MatterOpenRequest,
    NoteCreate, OnboardingRead, OnboardingUpdate, PortalAccessRead, PortalInviteCreate,
    TaskCreate, TaskRead, TaskUpdate, TimeEntryCreate, TimeEntryRead,
)
from app.schemas.matter import MatterRead
from app.services.crm import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/crm", tags=["crm"])


def _conflict_read(check, candidates: list[ConflictCandidate]) -> ConflictCheckRead:
    base = ConflictCheckRead.model_validate(check)
    base.candidates = [ConflictCandidateRead.model_validate(row) for row in candidates]
    return base


@router.get("/overview", response_model=CRMOverview)
async def overview(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)) -> CRMOverview:
    return CRMOverview(**await service.overview(db, actor))


@router.get("/leads", response_model=list[LeadRead])
async def leads(limit: int = Query(100, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [LeadRead.model_validate(row) for row in await service.list_leads(db, actor, limit)]


@router.post("/leads", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead(payload: LeadCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return LeadRead.model_validate(await service.create_lead(db, actor, payload))


@router.patch("/leads/{lead_id}", response_model=LeadRead)
async def patch_lead(lead_id: UUID, payload: LeadUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return LeadRead.model_validate(await service.update_lead(db, actor, lead_id, payload))


@router.post("/leads/{lead_id}/convert", response_model=ClientRead)
async def convert_lead(lead_id: UUID, payload: ConvertLeadRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientRead.model_validate(await service.convert_lead(db, actor, lead_id, client_type=payload.client_type, legal_name=payload.legal_name))


@router.get("/clients", response_model=list[ClientRead])
async def clients(limit: int = Query(100, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ClientRead.model_validate(row) for row in await service.list_clients(db, actor, limit)]


@router.post("/clients", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(payload: ClientCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientRead.model_validate(await service.create_client(db, actor, payload))


@router.get("/clients/{client_id}", response_model=ClientDetail)
async def get_client(client_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    data = await service.client_detail(db, actor, client_id)
    return ClientDetail(
        client=ClientRead.model_validate(data["client"]),
        onboarding=OnboardingRead.model_validate(data["onboarding"]),
        contacts=[ContactRead.model_validate(row) for row in data["contacts"]],
        kyc=[KYCRecordRead.model_validate(row) for row in data["kyc"]],
        engagements=[EngagementRead.model_validate(row) for row in data["engagements"]],
        matters=[ClientMatterSummary.model_validate(row) for row in data["matters"]],
        notes=[ClientNoteRead(id=str(row.id), title=row.title, body=row.body, matter_id=str(row.matter_id) if row.matter_id else None, is_private=row.is_private, created_at=row.created_at) for row in data["notes"]],
        communications=[ClientCommunicationRead(id=str(row.id), type=row.communication_type.value, occurred_at=row.occurred_at, direction=row.direction, subject=row.subject, summary=row.summary, matter_id=str(row.matter_id) if row.matter_id else None) for row in data["communications"]],
        portal_access=[PortalAccessRead.model_validate(row) for row in data["portal_access"]],
    )


@router.patch("/clients/{client_id}", response_model=ClientRead)
async def patch_client(client_id: UUID, payload: ClientUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientRead.model_validate(await service.update_client(db, actor, client_id, payload))


@router.post("/clients/{client_id}/contacts", response_model=ContactRead, status_code=201)
async def add_contact(client_id: UUID, payload: ContactCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ContactRead.model_validate(await service.add_contact(db, actor, client_id, payload))


@router.get("/clients/{client_id}/onboarding", response_model=OnboardingRead)
async def onboarding(client_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return OnboardingRead.model_validate(await service.get_onboarding(db, actor, client_id))


@router.patch("/clients/{client_id}/onboarding", response_model=OnboardingRead)
async def patch_onboarding(client_id: UUID, payload: OnboardingUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row = await service.update_onboarding(db, actor, client_id, address_complete=payload.address_complete, engagement_complete=payload.engagement_complete, notes=payload.notes, mark_complete=payload.mark_complete)
    return OnboardingRead.model_validate(row)


@router.post("/clients/{client_id}/kyc", response_model=KYCRecordRead, status_code=201)
async def create_kyc(client_id: UUID, payload: KYCRecordCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KYCRecordRead.model_validate(await service.create_kyc(db, actor, client_id, payload))


@router.patch("/kyc/{record_id}", response_model=KYCRecordRead)
async def review_kyc(record_id: UUID, payload: KYCVerifyRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KYCRecordRead.model_validate(await service.verify_kyc(db, actor, record_id, payload.status, payload.notes))


@router.post("/clients/{client_id}/engagements", response_model=EngagementRead, status_code=201)
async def engagement(client_id: UUID, payload: EngagementCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return EngagementRead.model_validate(await service.create_engagement(db, actor, client_id, payload))


@router.post("/clients/{client_id}/matters", response_model=MatterRead, status_code=201)
async def open_matter(client_id: UUID, payload: MatterOpenRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return MatterRead.model_validate(await service.open_matter(db, actor, client_id, payload))


@router.post("/clients/{client_id}/notes", status_code=201)
async def note(client_id: UUID, payload: NoteCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row = await service.add_note(db, actor, client_id, payload)
    return {"id": row.id, "created_at": row.created_at}


@router.post("/clients/{client_id}/communications", status_code=201)
async def communication(client_id: UUID, payload: CommunicationCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row = await service.log_communication(db, actor, client_id, payload)
    return {"id": row.id, "occurred_at": row.occurred_at}


@router.post("/clients/{client_id}/portal", response_model=PortalAccessRead, status_code=201)
async def portal_invite(client_id: UUID, payload: PortalInviteCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return PortalAccessRead.model_validate(await service.invite_portal(db, actor, client_id, payload))


@router.get("/conflicts", response_model=list[ConflictCheckRead])
async def conflicts(limit: int = Query(100, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [_conflict_read(check, candidates) for check, candidates in await service.list_conflict_checks(db, actor, limit)]


@router.post("/conflicts", response_model=ConflictCheckRead, status_code=201)
async def conflict_check(payload: ConflictCheckCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    check, candidates = await service.run_conflict_check(db, actor, payload)
    return _conflict_read(check, candidates)


@router.patch("/conflicts/{check_id}", response_model=ConflictCheckRead)
async def review_conflict(check_id: UUID, payload: ConflictDecision, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    check = await service.review_conflict_check(db, actor, check_id, decision=payload.status, note=payload.review_note)
    candidates = [candidates for c_check, candidates in await service.list_conflict_checks(db, actor, 500) if c_check.id == check.id]
    return _conflict_read(check, candidates[0] if candidates else [])


@router.get("/tasks", response_model=list[TaskRead])
async def tasks(limit: int = Query(100, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [TaskRead.model_validate(row) for row in await service.list_tasks(db, actor, limit)]


@router.post("/tasks", response_model=TaskRead, status_code=201)
async def create_task(payload: TaskCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return TaskRead.model_validate(await service.create_task(db, actor, payload))


@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def patch_task(task_id: UUID, payload: TaskUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return TaskRead.model_validate(await service.update_task(db, actor, task_id, payload))


@router.post("/time", response_model=TimeEntryRead, status_code=201)
async def time_entry(payload: TimeEntryCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return TimeEntryRead.model_validate(await service.add_time_entry(db, actor, payload))


@router.get("/clients/{client_id}/security", response_model=ClientSecurityRead)
async def client_security(client_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientSecurityRead.model_validate(await service.get_client_security(db, actor, client_id))


@router.patch("/clients/{client_id}/security", response_model=ClientSecurityRead)
async def patch_client_security(client_id: UUID, payload: ClientSecurityUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientSecurityRead.model_validate(await service.update_client_security(db, actor, client_id, classification=payload.classification, access_mode=payload.access_mode, notes=payload.notes))


@router.get("/clients/{client_id}/grants", response_model=list[ClientGrantRead])
async def client_grants(client_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ClientGrantRead.model_validate(row) for row in await service.list_client_grants(db, actor, client_id)]


@router.post("/clients/{client_id}/grants", response_model=ClientGrantRead, status_code=201)
async def client_grant(client_id: UUID, payload: ClientGrantCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientGrantRead.model_validate(await service.create_client_grant(db, actor, client_id, membership_id=payload.membership_id, effect=payload.effect, access_level=payload.access_level, reason=payload.reason))
