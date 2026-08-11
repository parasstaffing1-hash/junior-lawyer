from __future__ import annotations

import hmac
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.document import Document
from app.models.matter import Matter
from app.models.security import (
    AccessEffect,
    AuditOutcome,
    ConfidentialityLevel,
    DeletionRequest,
    DeletionStatus,
    DocumentAccessGrant,
    LegalHold,
    LegalHoldStatus,
    MatterAccessGrant,
    MatterAccessLevel,
    MatterAccessMode,
    MatterSecurityProfile,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSecurityPolicy,
    OrganizationStatus,
    RetentionPolicy,
    RetentionResourceType,
    SecurityAuditEntry,
    SecurityUser,
    UserSession,
    UserStatus,
)
from app.schemas.security import (
    BootstrapRequest,
    DeletionDecisionRequest,
    DeletionRequestCreate,
    DocumentGrantCreate,
    LegalHoldCreate,
    MatterGrantCreate,
    MatterSecurityProfileUpdate,
    SecurityPolicyUpdate,
    UserCreateRequest,
)
from app.services.security.audit import append_audit_event, verify_audit_chain
from app.services.security.context import ActorContext
from app.services.security.crypto import (
    hash_password,
    new_csrf_token,
    new_session_token,
    token_hash,
    verify_password,
    verify_token_hash,
    privacy_hash,
)
from app.services.security.permissions import SECURITY_MANAGER_ROLES, decide_matter_access


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Generated once; used only to make unknown-user login perform the same expensive scrypt path.
_DUMMY_HASH = hash_password("not-a-real-user-password-000000")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _validate_email(email: str) -> str:
    value = email.strip().casefold()
    if not EMAIL_RE.match(value):
        raise HTTPException(status_code=422, detail="A valid email address is required")
    return value


async def get_policy(db: AsyncSession, organization_id: UUID) -> OrganizationSecurityPolicy:
    policy = await db.scalar(
        select(OrganizationSecurityPolicy).where(
            OrganizationSecurityPolicy.organization_id == organization_id
        )
    )
    if policy:
        return policy
    policy = OrganizationSecurityPolicy(organization_id=organization_id)
    db.add(policy)
    await db.flush()
    return policy


async def bootstrap(db: AsyncSession, payload: BootstrapRequest) -> tuple[Organization, SecurityUser, OrganizationMembership]:
    if settings.app_env.casefold() == "production" and not settings.security_bootstrap_secret:
        raise HTTPException(status_code=503, detail="SECURITY_BOOTSTRAP_SECRET must be configured in production")
    existing = await db.scalar(select(func.count(Organization.id)))
    if existing:
        raise HTTPException(status_code=409, detail="Security bootstrap has already been completed")
    if settings.security_bootstrap_secret and not hmac.compare_digest(
        payload.bootstrap_secret or "", settings.security_bootstrap_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid bootstrap secret")
    email = _validate_email(payload.admin_email)
    organization = Organization(
        name=payload.organization_name.strip(),
        slug=payload.organization_slug.strip().casefold(),
        status=OrganizationStatus.ACTIVE,
    )
    db.add(organization)
    await db.flush()
    policy = OrganizationSecurityPolicy(organization_id=organization.id)
    db.add(policy)
    user = SecurityUser(
        email=email,
        display_name=payload.admin_name.strip(),
        password_hash=hash_password(payload.password),
        status=UserStatus.ACTIVE,
        password_changed_at=_now(),
    )
    db.add(user)
    await db.flush()
    membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
        status=MembershipStatus.ACTIVE,
        is_default=True,
    )
    db.add(membership)
    await db.flush()
    actor = ActorContext(
        user_id=user.id,
        membership_id=membership.id,
        organization_id=organization.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        mfa_enrolled=user.mfa_enrolled,
    )
    await append_audit_event(
        db,
        organization_id=organization.id,
        actor=actor,
        action="security.bootstrap",
        resource_type="organization",
        resource_id=str(organization.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"role": membership.role.value},
    )
    await db.commit()
    return organization, user, membership


async def _membership_for_login(
    db: AsyncSession,
    user: SecurityUser,
    organization_slug: str | None,
) -> OrganizationMembership | None:
    stmt = (
        select(OrganizationMembership)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
            Organization.status == OrganizationStatus.ACTIVE,
        )
        .options(selectinload(OrganizationMembership.organization))
        .order_by(OrganizationMembership.is_default.desc(), OrganizationMembership.created_at)
    )
    if organization_slug:
        stmt = stmt.where(Organization.slug == organization_slug.casefold())
    return await db.scalar(stmt.limit(1))


async def login(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    organization_slug: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[ActorContext, Organization, str, str, UserSession]:
    normalized = _validate_email(email)
    user = await db.scalar(select(SecurityUser).where(SecurityUser.email == normalized))
    if not user:
        verify_password(password, _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Invalid email, password, or organization")
    membership = await _membership_for_login(db, user, organization_slug)
    if not membership:
        verify_password(password, user.password_hash)
        raise HTTPException(status_code=401, detail="Invalid email, password, or organization")
    organization = membership.organization
    policy = await get_policy(db, organization.id)
    now = _now()
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="User account is disabled")
    if user.locked_until and _aware(user.locked_until) > now:
        raise HTTPException(status_code=423, detail="Account is temporarily locked")
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        locked = False
        if user.failed_login_attempts >= policy.max_failed_login_attempts:
            user.locked_until = now + timedelta(minutes=policy.lockout_minutes)
            user.failed_login_attempts = 0
            locked = True
        await append_audit_event(
            db,
            organization_id=organization.id,
            actor=None,
            action="auth.login",
            resource_type="session",
            outcome=AuditOutcome.FAILURE,
            reason="Invalid credentials",
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"email_hash": privacy_hash(normalized), "account_locked": locked},
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid email, password, or organization")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    token = new_session_token()
    csrf = new_csrf_token()
    absolute = now + timedelta(hours=policy.session_absolute_lifetime_hours)
    expires = min(now + timedelta(minutes=policy.session_idle_timeout_minutes), absolute)
    session = UserSession(
        user_id=user.id,
        organization_id=organization.id,
        membership_id=membership.id,
        token_hash=token_hash(token),
        csrf_hash=token_hash(csrf),
        password_version=user.password_version,
        expires_at=expires,
        absolute_expires_at=absolute,
        last_seen_at=now,
        ip_hash=None,
        user_agent_hash=None,
    )
    session.ip_hash = privacy_hash(ip_address)
    session.user_agent_hash = privacy_hash(user_agent)
    db.add(session)
    await db.flush()

    active_sessions = list(
        (
            await db.scalars(
                select(UserSession)
                .where(
                    UserSession.user_id == user.id,
                    UserSession.organization_id == organization.id,
                    UserSession.revoked_at.is_(None),
                    UserSession.id != session.id,
                )
                .order_by(UserSession.last_seen_at.asc())
            )
        ).all()
    )
    overflow = max(0, len(active_sessions) - policy.max_concurrent_sessions + 1)
    for old in active_sessions[:overflow]:
        old.revoked_at = now
        old.revoked_reason = "Concurrent session limit"

    actor = ActorContext(
        user_id=user.id,
        membership_id=membership.id,
        organization_id=organization.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        mfa_enrolled=user.mfa_enrolled,
        session_id=session.id,
    )
    await append_audit_event(
        db,
        organization_id=organization.id,
        actor=actor,
        action="auth.login",
        resource_type="session",
        resource_id=str(session.id),
        outcome=AuditOutcome.SUCCESS,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()
    return actor, organization, token, csrf, session


async def authenticate_session(
    db: AsyncSession,
    token: str,
    *,
    touch: bool = True,
) -> tuple[ActorContext, UserSession] | None:
    if not token:
        return None
    session = await db.scalar(
        select(UserSession)
        .where(UserSession.token_hash == token_hash(token))
        .options(
            selectinload(UserSession.user),
            selectinload(UserSession.membership),
        )
    )
    if not session:
        return None
    now = _now()
    user = session.user
    membership = session.membership
    if (
        session.revoked_at
        or _aware(session.expires_at) <= now
        or _aware(session.absolute_expires_at) <= now
        or user.status != UserStatus.ACTIVE
        or membership.status != MembershipStatus.ACTIVE
        or session.password_version != user.password_version
    ):
        return None
    actor = ActorContext(
        user_id=user.id,
        membership_id=membership.id,
        organization_id=session.organization_id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        mfa_enrolled=user.mfa_enrolled,
        session_id=session.id,
    )
    if touch:
        policy = await get_policy(db, session.organization_id)
        last_seen = _aware(session.last_seen_at)
        if (now - last_seen).total_seconds() >= settings.security_session_touch_seconds:
            session.last_seen_at = now
            session.expires_at = min(
                now + timedelta(minutes=policy.session_idle_timeout_minutes),
                _aware(session.absolute_expires_at),
            )
            await db.commit()
    return actor, session


def csrf_valid(session: UserSession, token: str | None) -> bool:
    return bool(token and verify_token_hash(token, session.csrf_hash))


async def revoke_session(db: AsyncSession, session_id: UUID, actor: ActorContext, reason: str = "Logout") -> None:
    session = await db.get(UserSession, session_id)
    if not session or session.user_id != actor.user_id:
        return
    session.revoked_at = _now()
    session.revoked_reason = reason
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="auth.logout",
        resource_type="session",
        resource_id=str(session.id),
        outcome=AuditOutcome.SUCCESS,
    )
    await db.commit()


def _require_security_manager(actor: ActorContext) -> None:
    if actor.role not in SECURITY_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Organization security administrator role required")


async def create_user(db: AsyncSession, actor: ActorContext, payload: UserCreateRequest) -> tuple[SecurityUser, OrganizationMembership]:
    _require_security_manager(actor)
    email = _validate_email(payload.email)
    if await db.scalar(select(SecurityUser).where(SecurityUser.email == email)):
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    policy = await get_policy(db, actor.organization_id)
    if len(payload.password) < policy.password_min_length:
        raise HTTPException(status_code=422, detail=f"Password must be at least {policy.password_min_length} characters")
    user = SecurityUser(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        locale=payload.locale,
        password_changed_at=_now(),
    )
    db.add(user)
    await db.flush()
    membership = OrganizationMembership(
        organization_id=actor.organization_id,
        user_id=user.id,
        role=payload.role,
        status=MembershipStatus.ACTIVE,
    )
    db.add(membership)
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="member.create",
        resource_type="user",
        resource_id=str(user.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"role": payload.role.value},
    )
    await db.commit()
    return user, membership


async def get_or_create_matter_profile(db: AsyncSession, actor: ActorContext, matter_id: UUID) -> MatterSecurityProfile:
    matter = await db.get(Matter, matter_id)
    if not matter or matter.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Matter not found")
    profile = await db.scalar(select(MatterSecurityProfile).where(MatterSecurityProfile.matter_id == matter_id))
    if not profile:
        profile = MatterSecurityProfile(matter_id=matter_id, created_by_user_id=actor.user_id)
        db.add(profile)
        await db.flush()
    return profile


async def update_matter_profile(db: AsyncSession, actor: ActorContext, matter_id: UUID, payload: MatterSecurityProfileUpdate) -> MatterSecurityProfile:
    _require_security_manager(actor)
    profile = await get_or_create_matter_profile(db, actor, matter_id)
    data = payload.model_dump(exclude_unset=True)
    making_explicit = (
        data.get("access_mode") == MatterAccessMode.EXPLICIT
        or data.get("classification") == ConfidentialityLevel.ETHICAL_WALL
    )
    if making_explicit:
        grant = await db.scalar(select(MatterAccessGrant).where(
            MatterAccessGrant.matter_id == matter_id,
            MatterAccessGrant.membership_id == actor.membership_id,
        ))
        if grant is None:
            grant = MatterAccessGrant(
                matter_id=matter_id, membership_id=actor.membership_id,
                effect=AccessEffect.ALLOW, access_level=MatterAccessLevel.MANAGE, granted_by_user_id=actor.user_id,
                reason="Automatic administrator grant before enabling explicit confidentiality",
            )
            db.add(grant)
        else:
            grant.effect = AccessEffect.ALLOW
            grant.access_level = MatterAccessLevel.MANAGE
    for field, value in data.items():
        setattr(profile, field, value)
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="matter.security.update",
        resource_type="matter",
        resource_id=str(matter_id),
        outcome=AuditOutcome.SUCCESS,
        metadata=payload.model_dump(mode="json", exclude_unset=True),
    )
    await db.commit()
    await db.refresh(profile)
    return profile


async def list_matter_grants(db: AsyncSession, actor: ActorContext, matter_id: UUID) -> list[MatterAccessGrant]:
    _require_security_manager(actor)
    await get_or_create_matter_profile(db, actor, matter_id)
    return list((await db.scalars(select(MatterAccessGrant).where(MatterAccessGrant.matter_id == matter_id).order_by(MatterAccessGrant.created_at))).all())


async def upsert_matter_grant(db: AsyncSession, actor: ActorContext, matter_id: UUID, payload: MatterGrantCreate) -> MatterAccessGrant:
    _require_security_manager(actor)
    await get_or_create_matter_profile(db, actor, matter_id)
    membership = await db.get(OrganizationMembership, payload.membership_id)
    if not membership or membership.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Membership not found")
    grant = await db.scalar(select(MatterAccessGrant).where(MatterAccessGrant.matter_id == matter_id, MatterAccessGrant.membership_id == payload.membership_id))
    if not grant:
        grant = MatterAccessGrant(matter_id=matter_id, membership_id=payload.membership_id, granted_by_user_id=actor.user_id)
        db.add(grant)
    for field, value in payload.model_dump(exclude={"membership_id"}).items():
        setattr(grant, field, value)
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="matter.access.upsert",
        resource_type="matter",
        resource_id=str(matter_id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"membership_id": str(payload.membership_id), "effect": payload.effect.value, "level": payload.access_level.value},
    )
    await db.commit()
    await db.refresh(grant)
    return grant


async def upsert_document_grant(db: AsyncSession, actor: ActorContext, document_id: UUID, payload: DocumentGrantCreate) -> DocumentAccessGrant:
    _require_security_manager(actor)
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    decision = await decide_matter_access(db, actor, document.matter_id)
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    membership = await db.get(OrganizationMembership, payload.membership_id)
    if not membership or membership.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Membership not found")
    grant = await db.scalar(select(DocumentAccessGrant).where(DocumentAccessGrant.document_id == document_id, DocumentAccessGrant.membership_id == payload.membership_id))
    if not grant:
        grant = DocumentAccessGrant(document_id=document_id, membership_id=payload.membership_id, granted_by_user_id=actor.user_id)
        db.add(grant)
    for field, value in payload.model_dump(exclude={"membership_id"}).items():
        setattr(grant, field, value)
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="document.access.upsert",
        resource_type="document",
        resource_id=str(document_id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"membership_id": str(payload.membership_id), "effect": payload.effect.value, "level": payload.access_level.value},
    )
    await db.commit()
    await db.refresh(grant)
    return grant


async def update_policy(db: AsyncSession, actor: ActorContext, payload: SecurityPolicyUpdate) -> OrganizationSecurityPolicy:
    _require_security_manager(actor)
    policy = await get_policy(db, actor.organization_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="security.policy.update",
        resource_type="organization",
        resource_id=str(actor.organization_id),
        outcome=AuditOutcome.SUCCESS,
        metadata=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    await db.refresh(policy)
    return policy


async def create_legal_hold(db: AsyncSession, actor: ActorContext, payload: LegalHoldCreate) -> LegalHold:
    if actor.role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER, OrganizationRole.LAWYER}:
        raise HTTPException(status_code=403, detail="Insufficient role to place a legal hold")
    decision = await decide_matter_access(db, actor, payload.matter_id)
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    hold = LegalHold(
        organization_id=actor.organization_id,
        matter_id=payload.matter_id,
        label=payload.label,
        reason=payload.reason,
        created_by_user_id=actor.user_id,
    )
    db.add(hold)
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="legal_hold.create",
        resource_type="matter",
        resource_id=str(payload.matter_id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"label": payload.label},
    )
    await db.commit()
    await db.refresh(hold)
    return hold


async def release_legal_hold(db: AsyncSession, actor: ActorContext, hold_id: UUID) -> LegalHold:
    _require_security_manager(actor)
    hold = await db.get(LegalHold, hold_id)
    if not hold or hold.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Legal hold not found")
    hold.status = LegalHoldStatus.RELEASED
    hold.released_by_user_id = actor.user_id
    hold.released_at = _now()
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="legal_hold.release",
        resource_type="matter",
        resource_id=str(hold.matter_id),
        outcome=AuditOutcome.SUCCESS,
        metadata={"hold_id": str(hold.id)},
    )
    await db.commit()
    await db.refresh(hold)
    return hold


async def _active_hold_for_resource(db: AsyncSession, organization_id: UUID, resource_type: RetentionResourceType, resource_id: str) -> LegalHold | None:
    matter_id: UUID | None = None
    try:
        rid = UUID(resource_id)
    except ValueError:
        return None
    if resource_type == RetentionResourceType.MATTER:
        matter_id = rid
    elif resource_type == RetentionResourceType.DOCUMENT:
        document = await db.get(Document, rid)
        matter_id = document.matter_id if document else None
    elif resource_type in {RetentionResourceType.DRAFT, RetentionResourceType.CONTRACT, RetentionResourceType.AI_RUN}:
        # Foundation: these resource types should be resolved through their parent matter before execution.
        return None
    if matter_id is None:
        return None
    return await db.scalar(
        select(LegalHold).where(
            LegalHold.organization_id == organization_id,
            LegalHold.matter_id == matter_id,
            LegalHold.status == LegalHoldStatus.ACTIVE,
        )
    )


async def request_deletion(db: AsyncSession, actor: ActorContext, payload: DeletionRequestCreate) -> DeletionRequest:
    hold = await _active_hold_for_resource(db, actor.organization_id, payload.resource_type, payload.resource_id)
    row = DeletionRequest(
        organization_id=actor.organization_id,
        requested_by_user_id=actor.user_id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        reason=payload.reason,
        status=DeletionStatus.BLOCKED if hold else DeletionStatus.REQUESTED,
        hold_id=hold.id if hold else None,
        decision_reason="Active legal hold blocks deletion" if hold else None,
    )
    db.add(row)
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="deletion.request",
        resource_type=payload.resource_type.value,
        resource_id=payload.resource_id,
        outcome=AuditOutcome.DENIED if hold else AuditOutcome.SUCCESS,
        reason=row.decision_reason,
    )
    await db.commit()
    await db.refresh(row)
    return row


async def decide_deletion(db: AsyncSession, actor: ActorContext, request_id: UUID, payload: DeletionDecisionRequest) -> DeletionRequest:
    _require_security_manager(actor)
    row = await db.get(DeletionRequest, request_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Deletion request not found")
    if row.status in {DeletionStatus.EXECUTED, DeletionStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail="Deletion request is already final")
    hold = await _active_hold_for_resource(db, actor.organization_id, row.resource_type, row.resource_id)
    if payload.approve and hold:
        row.status = DeletionStatus.BLOCKED
        row.hold_id = hold.id
        row.decision_reason = "Active legal hold blocks deletion"
    elif payload.approve:
        row.status = DeletionStatus.APPROVED
        row.approved_by_user_id = actor.user_id
        row.approved_at = _now()
        row.decision_reason = payload.reason
    else:
        row.status = DeletionStatus.CANCELLED
        row.decision_reason = payload.reason or "Cancelled by security administrator"
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="deletion.decision",
        resource_type=row.resource_type.value,
        resource_id=row.resource_id,
        outcome=AuditOutcome.ALLOWED if row.status == DeletionStatus.APPROVED else AuditOutcome.DENIED,
        reason=row.decision_reason,
        metadata={"request_id": str(row.id), "status": row.status.value},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def list_members(db: AsyncSession, actor: ActorContext) -> list[OrganizationMembership]:
    return list(
        (
            await db.scalars(
                select(OrganizationMembership)
                .where(OrganizationMembership.organization_id == actor.organization_id)
                .options(selectinload(OrganizationMembership.user))
                .order_by(OrganizationMembership.created_at)
            )
        ).all()
    )


async def security_overview(db: AsyncSession, actor: ActorContext) -> dict:
    organization = await db.get(Organization, actor.organization_id)
    policy = await get_policy(db, actor.organization_id)
    members = await db.scalar(select(func.count(OrganizationMembership.id)).where(OrganizationMembership.organization_id == actor.organization_id))
    active_sessions = await db.scalar(select(func.count(UserSession.id)).where(UserSession.organization_id == actor.organization_id, UserSession.revoked_at.is_(None), UserSession.expires_at > _now()))
    restricted = await db.scalar(select(func.count(MatterSecurityProfile.id)).join(Matter, Matter.id == MatterSecurityProfile.matter_id).where(Matter.organization_id == actor.organization_id, MatterSecurityProfile.classification.in_([ConfidentialityLevel.HIGHLY_CONFIDENTIAL, ConfidentialityLevel.ETHICAL_WALL])))
    ethical = await db.scalar(select(func.count(MatterSecurityProfile.id)).join(Matter, Matter.id == MatterSecurityProfile.matter_id).where(Matter.organization_id == actor.organization_id, MatterSecurityProfile.classification == ConfidentialityLevel.ETHICAL_WALL))
    holds = await db.scalar(select(func.count(LegalHold.id)).where(LegalHold.organization_id == actor.organization_id, LegalHold.status == LegalHoldStatus.ACTIVE))
    deletions = await db.scalar(select(func.count(DeletionRequest.id)).where(DeletionRequest.organization_id == actor.organization_id, DeletionRequest.status.in_([DeletionStatus.REQUESTED, DeletionStatus.BLOCKED])))
    audit_entries = await db.scalar(select(func.count(SecurityAuditEntry.id)).where(SecurityAuditEntry.organization_id == actor.organization_id))
    return {
        "actor": actor,
        "organization": organization,
        "policy": policy,
        "members": members or 0,
        "active_sessions": active_sessions or 0,
        "restricted_matters": restricted or 0,
        "ethical_wall_matters": ethical or 0,
        "active_legal_holds": holds or 0,
        "pending_deletions": deletions or 0,
        "audit_entries": audit_entries or 0,
    }


async def verify_org_audit(db: AsyncSession, actor: ActorContext) -> dict:
    if actor.role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}:
        raise HTTPException(status_code=403, detail="Audit access is not permitted for this role")
    return await verify_audit_chain(db, actor.organization_id)


async def update_membership(
    db: AsyncSession,
    actor: ActorContext,
    membership_id: UUID,
    *,
    role: OrganizationRole | None = None,
    membership_status: MembershipStatus | None = None,
) -> OrganizationMembership:
    _require_security_manager(actor)
    row = await db.get(OrganizationMembership, membership_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Membership not found")
    if row.user_id == actor.user_id and membership_status == MembershipStatus.SUSPENDED:
        raise HTTPException(status_code=409, detail="You cannot suspend your own active membership")
    removing_owner = (
        row.role == OrganizationRole.OWNER
        and ((role is not None and role != OrganizationRole.OWNER) or membership_status == MembershipStatus.SUSPENDED)
    )
    if removing_owner:
        owner_count = await db.scalar(
            select(func.count(OrganizationMembership.id)).where(
                OrganizationMembership.organization_id == actor.organization_id,
                OrganizationMembership.role == OrganizationRole.OWNER,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
            )
        ) or 0
        if owner_count <= 1:
            raise HTTPException(status_code=409, detail="An organization must retain at least one active owner")
    if role is not None:
        row.role = role
    if membership_status is not None:
        row.status = membership_status
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="member.update",
        resource_type="membership",
        resource_id=str(row.id),
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "role": row.role.value,
            "status": row.status.value,
        },
    )
    await db.commit()
    await db.refresh(row)
    return row


async def upsert_retention_policy(
    db: AsyncSession,
    actor: ActorContext,
    *,
    resource_type: RetentionResourceType,
    retention_days: int,
    enabled: bool,
    auto_delete_enabled: bool,
    notes: str | None,
) -> RetentionPolicy:
    if actor.role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}:
        raise HTTPException(status_code=403, detail="Retention policy access is not permitted for this role")
    row = await db.scalar(
        select(RetentionPolicy).where(
            RetentionPolicy.organization_id == actor.organization_id,
            RetentionPolicy.resource_type == resource_type,
        )
    )
    if not row:
        row = RetentionPolicy(
            organization_id=actor.organization_id,
            resource_type=resource_type,
            retention_days=retention_days,
        )
        db.add(row)
    row.retention_days = retention_days
    row.enabled = enabled
    row.auto_delete_enabled = auto_delete_enabled
    row.notes = notes
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="retention.policy.upsert",
        resource_type="organization",
        resource_id=str(actor.organization_id),
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "resource_type": resource_type.value,
            "retention_days": retention_days,
            "auto_delete_enabled": auto_delete_enabled,
        },
    )
    await db.commit()
    await db.refresh(row)
    return row


async def adopt_legacy_matter(db: AsyncSession, actor: ActorContext, matter_id: UUID) -> Matter:
    _require_security_manager(actor)
    matter = await db.get(Matter, matter_id)
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    if matter.organization_id is not None and matter.organization_id != actor.organization_id:
        raise HTTPException(status_code=409, detail="Matter already belongs to another organization")
    matter.organization_id = actor.organization_id
    if matter.created_by_user_id is None:
        matter.created_by_user_id = actor.user_id
    profile = await db.scalar(select(MatterSecurityProfile).where(MatterSecurityProfile.matter_id == matter_id))
    if not profile:
        db.add(MatterSecurityProfile(matter_id=matter_id, created_by_user_id=actor.user_id))
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="matter.adopt_legacy",
        resource_type="matter",
        resource_id=str(matter_id),
        outcome=AuditOutcome.SUCCESS,
    )
    await db.commit()
    await db.refresh(matter)
    return matter
