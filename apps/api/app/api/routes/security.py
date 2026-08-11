from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.document import Document
from app.models.matter import Matter
from app.models.security import (
    DeletionRequest,
    DocumentAccessGrant,
    LegalHold,
    Organization,
    RetentionPolicy,
    SecurityAuditEntry,
)
from app.schemas.security import (
    AccessDecisionRead,
    ActorRead,
    AuditEntryRead,
    AuditVerifyRead,
    BootstrapRequest,
    DeletionDecisionRequest,
    DeletionRequestCreate,
    DeletionRequestRead,
    DocumentGrantCreate,
    DocumentGrantRead,
    LegalHoldCreate,
    LegalHoldRead,
    LoginRequest,
    LoginResponse,
    MatterGrantCreate,
    MatterGrantRead,
    MatterSecurityProfileRead,
    MatterSecurityProfileUpdate,
    MembershipRead,
    MembershipUpdateRequest,
    OrganizationRead,
    RetentionPolicyCreate,
    RetentionPolicyRead,
    SecurityOverviewRead,
    SecurityPolicyRead,
    SecurityPolicyUpdate,
    UserCreateRequest,
)
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor
from app.services.security.permissions import (
    AUDIT_VIEWER_ROLES,
    RETENTION_MANAGER_ROLES,
    SECURITY_MANAGER_ROLES,
    decide_matter_access,
    visible_matter_ids,
)
from app.services.security import service


router = APIRouter(prefix="/security", tags=["security"])


@router.post("/bootstrap", status_code=status.HTTP_201_CREATED)
async def bootstrap(payload: BootstrapRequest, db: AsyncSession = Depends(get_db)) -> dict:
    organization, user, membership = await service.bootstrap(db, payload)
    return {
        "organization": OrganizationRead.model_validate(organization),
        "admin": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "membership_id": str(membership.id),
            "role": membership.role.value,
        },
        "message": "Security bootstrap complete. Sign in with the owner account.",
    }


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    actor, organization, raw_token, csrf, session = await service.login(
        db,
        email=payload.email,
        password=payload.password,
        organization_slug=payload.organization_slug,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    response.set_cookie(
        settings.security_session_cookie_name,
        raw_token,
        httponly=True,
        secure=settings.security_cookie_secure,
        samesite=settings.security_cookie_samesite,
        path="/",
    )
    response.set_cookie(
        "jl_csrf",
        csrf,
        httponly=False,
        secure=settings.security_cookie_secure,
        samesite=settings.security_cookie_samesite,
        path="/",
    )
    return LoginResponse(
        actor=ActorRead.model_validate(actor, from_attributes=True),
        organization=OrganizationRead.model_validate(organization),
        csrf_token=csrf,
        expires_at=session.expires_at,
        absolute_expires_at=session.absolute_expires_at,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> None:
    if actor.session_id:
        await service.revoke_session(db, actor.session_id, actor)
    response.delete_cookie(settings.security_session_cookie_name, path="/")
    response.delete_cookie("jl_csrf", path="/")


@router.get("/me", response_model=ActorRead)
async def me(actor: ActorContext = Depends(require_actor)) -> ActorRead:
    return ActorRead.model_validate(actor, from_attributes=True)


@router.get("/overview", response_model=SecurityOverviewRead)
async def overview(
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> SecurityOverviewRead:
    data = await service.security_overview(db, actor)
    return SecurityOverviewRead(
        actor=ActorRead.model_validate(data["actor"], from_attributes=True),
        organization=OrganizationRead.model_validate(data["organization"]),
        policy=SecurityPolicyRead.model_validate(data["policy"]),
        members=data["members"],
        active_sessions=data["active_sessions"],
        restricted_matters=data["restricted_matters"],
        ethical_wall_matters=data["ethical_wall_matters"],
        active_legal_holds=data["active_legal_holds"],
        pending_deletions=data["pending_deletions"],
        audit_entries=data["audit_entries"],
    )


@router.get("/members", response_model=list[MembershipRead])
async def members(
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> list[MembershipRead]:
    return [MembershipRead.model_validate(row) for row in await service.list_members(db, actor)]


@router.post("/members", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
async def create_member(
    payload: UserCreateRequest,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> MembershipRead:
    _, membership = await service.create_user(db, actor, payload)
    rows = await service.list_members(db, actor)
    return MembershipRead.model_validate(next(item for item in rows if item.id == membership.id))


@router.patch("/members/{membership_id}", response_model=MembershipRead)
async def update_member(
    membership_id: UUID,
    payload: MembershipUpdateRequest,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> MembershipRead:
    row = await service.update_membership(
        db,
        actor,
        membership_id,
        role=payload.role,
        membership_status=payload.status,
    )
    # Reload through member list so the nested user is available.
    rows = await service.list_members(db, actor)
    return MembershipRead.model_validate(next(item for item in rows if item.id == row.id))


@router.get("/policy", response_model=SecurityPolicyRead)
async def policy(
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> SecurityPolicyRead:
    return SecurityPolicyRead.model_validate(await service.get_policy(db, actor.organization_id))


@router.patch("/policy", response_model=SecurityPolicyRead)
async def patch_policy(
    payload: SecurityPolicyUpdate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> SecurityPolicyRead:
    return SecurityPolicyRead.model_validate(await service.update_policy(db, actor, payload))




@router.get("/legacy-matters")
async def legacy_matters(
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if actor.role not in SECURITY_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Organization security administrator role required")
    rows = (await db.scalars(select(Matter).where(Matter.organization_id.is_(None)).order_by(Matter.created_at.desc()))).all()
    return [{
        "id": str(row.id), "title": row.title, "reference_number": row.reference_number,
        "case_number": row.case_number, "created_at": row.created_at.isoformat(),
    } for row in rows]


@router.post("/matters/{matter_id}/adopt")
async def adopt_legacy_matter(
    matter_id: UUID,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> dict:
    matter = await service.adopt_legacy_matter(db, actor, matter_id)
    return {"matter_id": str(matter.id), "organization_id": str(matter.organization_id), "adopted": True}


@router.get("/matters/{matter_id}/profile", response_model=MatterSecurityProfileRead)
async def matter_profile(
    matter_id: UUID,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> MatterSecurityProfileRead:
    return MatterSecurityProfileRead.model_validate(await service.get_or_create_matter_profile(db, actor, matter_id))


@router.patch("/matters/{matter_id}/profile", response_model=MatterSecurityProfileRead)
async def patch_matter_profile(
    matter_id: UUID,
    payload: MatterSecurityProfileUpdate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> MatterSecurityProfileRead:
    return MatterSecurityProfileRead.model_validate(await service.update_matter_profile(db, actor, matter_id, payload))


@router.get("/matters/{matter_id}/access", response_model=AccessDecisionRead)
async def matter_access(
    matter_id: UUID,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> AccessDecisionRead:
    decision = await decide_matter_access(db, actor, matter_id)
    return AccessDecisionRead(
        allowed=decision.allowed, reason=decision.reason,
        matter_access_level=decision.matter_access_level,
        remote_ai_allowed=decision.remote_ai_allowed,
        export_allowed=decision.export_allowed,
        classification=decision.classification,
    )


@router.get("/matters/{matter_id}/grants", response_model=list[MatterGrantRead])
async def matter_grants(
    matter_id: UUID,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> list[MatterGrantRead]:
    return [MatterGrantRead.model_validate(row) for row in await service.list_matter_grants(db, actor, matter_id)]


@router.post("/matters/{matter_id}/grants", response_model=MatterGrantRead)
async def upsert_matter_grant(
    matter_id: UUID,
    payload: MatterGrantCreate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> MatterGrantRead:
    return MatterGrantRead.model_validate(await service.upsert_matter_grant(db, actor, matter_id, payload))


@router.get("/documents/{document_id}/grants", response_model=list[DocumentGrantRead])
async def document_grants(
    document_id: UUID,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentGrantRead]:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    decision = await decide_matter_access(db, actor, document.matter_id)
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason or "Document access denied")
    rows = (await db.scalars(select(DocumentAccessGrant).where(DocumentAccessGrant.document_id == document_id))).all()
    return [DocumentGrantRead.model_validate(row) for row in rows]


@router.post("/documents/{document_id}/grants", response_model=DocumentGrantRead)
async def upsert_document_grant(
    document_id: UUID,
    payload: DocumentGrantCreate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> DocumentGrantRead:
    return DocumentGrantRead.model_validate(await service.upsert_document_grant(db, actor, document_id, payload))


@router.get("/audit", response_model=list[AuditEntryRead])
async def audit(
    limit: int = Query(default=100, ge=1, le=500),
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEntryRead]:
    if actor.role not in AUDIT_VIEWER_ROLES:
        raise HTTPException(status_code=403, detail="Audit access is not permitted for this role")
    rows = (
        await db.scalars(
            select(SecurityAuditEntry)
            .where(SecurityAuditEntry.organization_id == actor.organization_id)
            .order_by(SecurityAuditEntry.sequence.desc())
            .limit(limit)
        )
    ).all()
    return [AuditEntryRead.model_validate(row) for row in rows]


@router.get("/audit/verify", response_model=AuditVerifyRead)
async def verify_audit(
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> AuditVerifyRead:
    return AuditVerifyRead.model_validate(await service.verify_org_audit(db, actor))


@router.get("/retention", response_model=list[RetentionPolicyRead])
async def retention(
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> list[RetentionPolicyRead]:
    if actor.role not in RETENTION_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Retention policy access is not permitted for this role")
    rows = (await db.scalars(select(RetentionPolicy).where(RetentionPolicy.organization_id == actor.organization_id).order_by(RetentionPolicy.resource_type))).all()
    return [RetentionPolicyRead.model_validate(row) for row in rows]


@router.post("/retention", response_model=RetentionPolicyRead)
async def upsert_retention(
    payload: RetentionPolicyCreate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> RetentionPolicyRead:
    row = await service.upsert_retention_policy(
        db,
        actor,
        resource_type=payload.resource_type,
        retention_days=payload.retention_days,
        enabled=payload.enabled,
        auto_delete_enabled=payload.auto_delete_enabled,
        notes=payload.notes,
    )
    return RetentionPolicyRead.model_validate(row)


@router.get("/legal-holds", response_model=list[LegalHoldRead])
async def legal_holds(
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> list[LegalHoldRead]:
    stmt = select(LegalHold).where(LegalHold.organization_id == actor.organization_id)
    if actor.role not in RETENTION_MANAGER_ROLES:
        visible = await visible_matter_ids(db, actor)
        if not visible:
            return []
        stmt = stmt.where(LegalHold.matter_id.in_(visible))
    rows = (await db.scalars(stmt.order_by(LegalHold.created_at.desc()))).all()
    return [LegalHoldRead.model_validate(row) for row in rows]


@router.post("/legal-holds", response_model=LegalHoldRead, status_code=status.HTTP_201_CREATED)
async def create_hold(
    payload: LegalHoldCreate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> LegalHoldRead:
    return LegalHoldRead.model_validate(await service.create_legal_hold(db, actor, payload))


@router.patch("/legal-holds/{hold_id}/release", response_model=LegalHoldRead)
async def release_hold(
    hold_id: UUID,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> LegalHoldRead:
    return LegalHoldRead.model_validate(await service.release_legal_hold(db, actor, hold_id))


@router.get("/deletions", response_model=list[DeletionRequestRead])
async def deletions(
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> list[DeletionRequestRead]:
    stmt = select(DeletionRequest).where(DeletionRequest.organization_id == actor.organization_id)
    if actor.role not in RETENTION_MANAGER_ROLES:
        stmt = stmt.where(DeletionRequest.requested_by_user_id == actor.user_id)
    rows = (await db.scalars(stmt.order_by(DeletionRequest.created_at.desc()))).all()
    return [DeletionRequestRead.model_validate(row) for row in rows]


@router.post("/deletions", response_model=DeletionRequestRead, status_code=status.HTTP_201_CREATED)
async def create_deletion(
    payload: DeletionRequestCreate,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> DeletionRequestRead:
    return DeletionRequestRead.model_validate(await service.request_deletion(db, actor, payload))


@router.patch("/deletions/{request_id}", response_model=DeletionRequestRead)
async def decide_deletion(
    request_id: UUID,
    payload: DeletionDecisionRequest,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> DeletionRequestRead:
    return DeletionRequestRead.model_validate(await service.decide_deletion(db, actor, request_id, payload))
