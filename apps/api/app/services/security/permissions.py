from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.matter import Matter
from app.models.security import (
    AccessEffect,
    ConfidentialityLevel,
    DocumentAccessGrant,
    DocumentAccessLevel,
    MatterAccessGrant,
    MatterAccessLevel,
    MatterAccessMode,
    MatterSecurityProfile,
    OrganizationRole,
    OrganizationSecurityPolicy,
    PolicyDecision,
)
from app.services.security.context import ActorContext, get_current_actor


ROLE_BASE_LEVEL: dict[OrganizationRole, MatterAccessLevel | None] = {
    OrganizationRole.OWNER: MatterAccessLevel.MANAGE,
    OrganizationRole.ADMIN: MatterAccessLevel.MANAGE,
    OrganizationRole.PARTNER: MatterAccessLevel.MANAGE,
    OrganizationRole.LAWYER: MatterAccessLevel.WORK,
    OrganizationRole.JUNIOR: MatterAccessLevel.WORK,
    OrganizationRole.PARALEGAL: MatterAccessLevel.WORK,
    OrganizationRole.BILLING: None,
    OrganizationRole.READ_ONLY: MatterAccessLevel.VIEW,
}

SECURITY_MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}
MEMBER_MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}
RETENTION_MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}
AUDIT_VIEWER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}

_LEVEL = {MatterAccessLevel.VIEW: 1, MatterAccessLevel.WORK: 2, MatterAccessLevel.MANAGE: 3}
_DOC_LEVEL = {DocumentAccessLevel.VIEW: 1, DocumentAccessLevel.DOWNLOAD: 2, DocumentAccessLevel.EDIT: 3}


@dataclass(slots=True)
class AccessDecision:
    allowed: bool
    reason: str
    matter_access_level: MatterAccessLevel | None = None
    remote_ai_allowed: bool | None = None
    export_allowed: bool | None = None
    classification: ConfidentialityLevel | None = None


async def _profile(db: AsyncSession, matter_id: UUID) -> MatterSecurityProfile | None:
    return await db.scalar(select(MatterSecurityProfile).where(MatterSecurityProfile.matter_id == matter_id))


async def _policy(db: AsyncSession, organization_id: UUID) -> OrganizationSecurityPolicy | None:
    return await db.scalar(
        select(OrganizationSecurityPolicy).where(
            OrganizationSecurityPolicy.organization_id == organization_id
        )
    )


def _active(expires_at) -> bool:
    if expires_at is None:
        return True
    now = datetime.now(timezone.utc)
    value = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    return value > now


async def decide_matter_access(
    db: AsyncSession,
    actor: ActorContext,
    matter_id: UUID,
    *,
    required: MatterAccessLevel = MatterAccessLevel.VIEW,
) -> AccessDecision:
    matter = await db.get(Matter, matter_id)
    if not matter:
        return AccessDecision(False, "Matter not found")
    if matter.organization_id is None:
        return AccessDecision(False, "Matter is not assigned to an organization")
    if matter.organization_id != actor.organization_id:
        return AccessDecision(False, "Matter belongs to another organization")

    profile = await _profile(db, matter_id)
    classification = profile.classification if profile else ConfidentialityLevel.CONFIDENTIAL
    access_mode = profile.access_mode if profile else MatterAccessMode.ORGANIZATION

    grant = await db.scalar(
        select(MatterAccessGrant).where(
            MatterAccessGrant.matter_id == matter_id,
            MatterAccessGrant.membership_id == actor.membership_id,
        )
    )
    if grant and not _active(grant.expires_at):
        grant = None
    if grant and grant.effect == AccessEffect.DENY:
        return AccessDecision(False, "Access is explicitly denied", classification=classification)

    explicit_required = (
        access_mode == MatterAccessMode.EXPLICIT
        or classification == ConfidentialityLevel.ETHICAL_WALL
    )
    if explicit_required and not grant:
        return AccessDecision(
            False,
            "This matter is behind an explicit confidentiality wall",
            classification=classification,
        )

    level = grant.access_level if grant else ROLE_BASE_LEVEL.get(actor.role)
    if level is None or _LEVEL[level] < _LEVEL[required]:
        return AccessDecision(
            False,
            f"{required.value} access is required",
            matter_access_level=level,
            classification=classification,
        )

    policy = await _policy(db, actor.organization_id)
    remote_allowed = bool(policy and policy.allow_remote_ai_default)
    export_allowed = True if policy is None else policy.allow_exports_default
    if profile:
        if profile.remote_ai_policy == PolicyDecision.ALLOW:
            remote_allowed = True
        elif profile.remote_ai_policy == PolicyDecision.DENY:
            remote_allowed = False
        if profile.export_policy == PolicyDecision.ALLOW:
            export_allowed = True
        elif profile.export_policy == PolicyDecision.DENY:
            export_allowed = False
    if grant:
        if grant.allow_remote_ai is not None:
            remote_allowed = grant.allow_remote_ai
        if grant.allow_export is not None:
            export_allowed = grant.allow_export
    if policy and policy.require_mfa_for_remote_ai and not actor.mfa_enrolled:
        remote_allowed = False
    if (
        classification in {ConfidentialityLevel.HIGHLY_CONFIDENTIAL, ConfidentialityLevel.ETHICAL_WALL}
        and policy
        and policy.require_mfa_for_highly_confidential
        and not actor.mfa_enrolled
    ):
        remote_allowed = False
        export_allowed = False

    return AccessDecision(
        True,
        "Access allowed",
        matter_access_level=level,
        remote_ai_allowed=remote_allowed,
        export_allowed=export_allowed,
        classification=classification,
    )


async def decide_document_access(
    db: AsyncSession,
    actor: ActorContext,
    document_id: UUID,
    *,
    required: DocumentAccessLevel = DocumentAccessLevel.VIEW,
) -> AccessDecision:
    document = await db.get(Document, document_id)
    if not document:
        return AccessDecision(False, "Document not found")
    matter_required = MatterAccessLevel.WORK if required == DocumentAccessLevel.EDIT else MatterAccessLevel.VIEW
    matter_decision = await decide_matter_access(db, actor, document.matter_id, required=matter_required)
    if not matter_decision.allowed:
        return matter_decision

    grant = await db.scalar(
        select(DocumentAccessGrant).where(
            DocumentAccessGrant.document_id == document_id,
            DocumentAccessGrant.membership_id == actor.membership_id,
        )
    )
    if grant and not _active(grant.expires_at):
        grant = None
    if grant and grant.effect == AccessEffect.DENY:
        return AccessDecision(False, "Document access is explicitly denied")
    if grant and _DOC_LEVEL[grant.access_level] < _DOC_LEVEL[required]:
        return AccessDecision(False, f"{required.value} document access is required")
    return matter_decision


async def visible_matter_ids(db: AsyncSession, actor: ActorContext) -> set[UUID]:
    ids = set(
        (await db.scalars(select(Matter.id).where(Matter.organization_id == actor.organization_id))).all()
    )
    visible: set[UUID] = set()
    for matter_id in ids:
        decision = await decide_matter_access(db, actor, matter_id)
        if decision.allowed:
            visible.add(matter_id)
    return visible


async def remote_ai_allowed(db: AsyncSession, actor: ActorContext, matter_id: UUID) -> AccessDecision:
    decision = await decide_matter_access(db, actor, matter_id, required=MatterAccessLevel.WORK)
    if not decision.allowed:
        return decision
    if not decision.remote_ai_allowed:
        return AccessDecision(
            False,
            "Remote AI is blocked by organization, matter, grant, or MFA policy",
            matter_access_level=decision.matter_access_level,
            remote_ai_allowed=False,
            export_allowed=decision.export_allowed,
            classification=decision.classification,
        )
    return decision


async def enforce_current_matter_access(
    db: AsyncSession,
    matter_id: UUID,
    *,
    required: MatterAccessLevel = MatterAccessLevel.VIEW,
) -> None:
    actor = get_current_actor()
    if actor is None:
        return
    decision = await decide_matter_access(db, actor, matter_id, required=required)
    if not decision.allowed:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)

async def decide_client_access(
    db: AsyncSession,
    actor: ActorContext,
    client_id: UUID,
    *,
    required: MatterAccessLevel = MatterAccessLevel.VIEW,
) -> AccessDecision:
    # Imported lazily to keep the security core independent from the optional CRM module at import time.
    from app.models.crm import Client, ClientAccessGrant, ClientSecurityProfile

    client = await db.get(Client, client_id)
    if not client:
        return AccessDecision(False, "Client not found")
    if client.organization_id != actor.organization_id:
        return AccessDecision(False, "Client belongs to another organization")
    profile = await db.scalar(select(ClientSecurityProfile).where(ClientSecurityProfile.client_id == client_id))
    classification = profile.classification if profile else ConfidentialityLevel.CONFIDENTIAL
    access_mode = profile.access_mode if profile else MatterAccessMode.ORGANIZATION
    grant = await db.scalar(
        select(ClientAccessGrant).where(
            ClientAccessGrant.client_id == client_id,
            ClientAccessGrant.membership_id == actor.membership_id,
        )
    )
    if grant and not _active(grant.expires_at):
        grant = None
    if grant and grant.effect == AccessEffect.DENY:
        return AccessDecision(False, "Client access is explicitly denied", classification=classification)
    if (access_mode == MatterAccessMode.EXPLICIT or classification == ConfidentialityLevel.ETHICAL_WALL) and not grant:
        return AccessDecision(False, "This client is behind an explicit confidentiality wall", classification=classification)
    level = grant.access_level if grant else ROLE_BASE_LEVEL.get(actor.role)
    if level is None or _LEVEL[level] < _LEVEL[required]:
        return AccessDecision(False, f"{required.value} client access is required", matter_access_level=level, classification=classification)
    return AccessDecision(True, "Access allowed", matter_access_level=level, classification=classification)


async def visible_client_ids(db: AsyncSession, actor: ActorContext) -> set[UUID]:
    from app.models.crm import Client
    ids = set((await db.scalars(select(Client.id).where(Client.organization_id == actor.organization_id))).all())
    visible: set[UUID] = set()
    for client_id in ids:
        if (await decide_client_access(db, actor, client_id)).allowed:
            visible.add(client_id)
    return visible
