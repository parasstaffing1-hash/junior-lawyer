from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Invoice, InvoiceStatus, InvoiceVersion
from app.models.crm import Client, ClientAccessGrant, ClientPortalAccess, ClientSecurityProfile, MatterClientLink, PortalAccessStatus
from app.models.document import Document
from app.models.collaboration import ClientDocumentApprovalRequest, ClientDocumentApprovalStatus
from app.models.portal import (
    ClientPortalMessage, ClientPortalRequest, ClientPortalSession, ClientPortalShare, ClientPortalUser,
    PortalRequestStatus, PortalSenderType, PortalShareType, PortalUserStatus,
)
from app.models.security import AccessEffect, AuditOutcome, ConfidentialityLevel, DocumentAccessLevel, MatterAccessLevel, MatterAccessMode, Organization, OrganizationRole
from app.schemas.portal import PortalMessageCreate, PortalRequestCreate, PortalShareCreate
from app.services.documents.storage import resolve_storage_key
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext
from app.services.security.crypto import hash_password, new_csrf_token, new_session_token, privacy_hash, token_hash, verify_password, verify_token_hash
from app.services.security.permissions import decide_client_access, decide_document_access, decide_matter_access


PORTAL_MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER, OrganizationRole.LAWYER, OrganizationRole.BILLING}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class PortalActor:
    portal_user_id: UUID
    portal_access_id: UUID
    organization_id: UUID
    client_id: UUID
    email: str


async def _internal_access(db: AsyncSession, actor: ActorContext, access_id: UUID) -> ClientPortalAccess:
    if actor.role not in PORTAL_MANAGER_ROLES: raise HTTPException(403, "Your role does not permit client portal management")
    access = await db.get(ClientPortalAccess, access_id)
    if not access or access.organization_id != actor.organization_id: raise HTTPException(404, "Portal access not found")
    decision = await decide_client_access(db, actor, access.client_id, required=MatterAccessLevel.VIEW)
    if not decision.allowed:
        if actor.role != OrganizationRole.BILLING:
            raise HTTPException(403, decision.reason)
        profile = await db.scalar(select(ClientSecurityProfile).where(ClientSecurityProfile.client_id == access.client_id))
        if profile and (profile.access_mode == MatterAccessMode.EXPLICIT or profile.classification == ConfidentialityLevel.ETHICAL_WALL):
            grant = await db.scalar(select(ClientAccessGrant).where(
                ClientAccessGrant.client_id == access.client_id,
                ClientAccessGrant.membership_id == actor.membership_id,
                ClientAccessGrant.effect == AccessEffect.ALLOW,
            ))
            if not grant:
                raise HTTPException(403, "Restricted client portal access requires an explicit client grant")
    if access.status == PortalAccessStatus.REVOKED: raise HTTPException(409, "Portal access is revoked")
    return access


async def issue_activation_token(db: AsyncSession, actor: ActorContext, access_id: UUID) -> dict:
    access = await _internal_access(db, actor, access_id)
    raw = new_session_token()
    access.invite_token_hash = token_hash(raw)
    access.invite_expires_at = _now() + timedelta(hours=settings.portal_invite_hours)
    access.status = PortalAccessStatus.INVITED
    await append_audit_event(db, organization_id=actor.organization_id, actor=actor, action="portal.invite.rotate", resource_type="client_portal_access", resource_id=str(access.id), outcome=AuditOutcome.SUCCESS)
    await db.commit()
    return {"portal_access_id": str(access.id), "invite_token": raw, "expires_at": access.invite_expires_at}


async def _create_session(db: AsyncSession, user: ClientPortalUser, request: Request | None = None) -> tuple[str, str, ClientPortalSession]:
    raw = new_session_token(); csrf = new_csrf_token(); now = _now()
    session = ClientPortalSession(
        portal_user_id=user.id, token_hash=token_hash(raw), csrf_hash=token_hash(csrf),
        expires_at=now + timedelta(hours=settings.portal_session_hours), last_seen_at=now,
        ip_hash=privacy_hash(request.client.host if request and request.client else None),
        user_agent_hash=privacy_hash(request.headers.get("user-agent") if request else None),
    )
    db.add(session); user.last_login_at = now; await db.flush()
    return raw, csrf, session


async def activate(db: AsyncSession, invite_token: str, password: str, request: Request | None = None):
    digest = token_hash(invite_token)
    access = await db.scalar(select(ClientPortalAccess).where(ClientPortalAccess.invite_token_hash == digest))
    if not access or access.status == PortalAccessStatus.REVOKED: raise HTTPException(400, "Invitation is invalid")
    if not access.invite_expires_at or _aware(access.invite_expires_at) <= _now(): raise HTTPException(400, "Invitation has expired")
    existing_email = await db.scalar(select(ClientPortalUser).where(ClientPortalUser.organization_id == access.organization_id, ClientPortalUser.email == access.email.casefold()))
    if existing_email and existing_email.portal_access_id != access.id:
        raise HTTPException(409, "This email already has a client portal identity for the firm")
    user = existing_email or await db.scalar(select(ClientPortalUser).where(ClientPortalUser.portal_access_id == access.id))
    if user:
        user.password_hash = hash_password(password); user.status = PortalUserStatus.ACTIVE
    else:
        user = ClientPortalUser(organization_id=access.organization_id, client_id=access.client_id, portal_access_id=access.id, email=access.email.casefold(), password_hash=hash_password(password), status=PortalUserStatus.ACTIVE)
        db.add(user); await db.flush()
    access.status = PortalAccessStatus.ACTIVE; access.activated_at = _now(); access.invite_token_hash = None; access.invite_expires_at = None
    raw, csrf, session = await _create_session(db, user, request)
    await append_audit_event(db, organization_id=access.organization_id, action="portal.activate", resource_type="client_portal_access", resource_id=str(access.id), outcome=AuditOutcome.SUCCESS, metadata={"email_hash": privacy_hash(access.email)})
    await db.commit(); return user, raw, csrf, session


async def login(db: AsyncSession, *, organization_slug: str, email: str, password: str, request: Request | None = None):
    org = await db.scalar(select(Organization).where(Organization.slug == organization_slug.strip().casefold()))
    normalized = email.strip().casefold()
    user = await db.scalar(select(ClientPortalUser).where(ClientPortalUser.organization_id == (org.id if org else UUID(int=0)), ClientPortalUser.email == normalized)) if org else None
    # Perform a hash path even when account is absent to reduce obvious timing differences.
    if not user:
        hash_password("portal-dummy-password-do-not-use", n=16384, r=8, p=1)
        raise HTTPException(401, "Invalid portal credentials")
    access = await db.get(ClientPortalAccess, user.portal_access_id)
    if user.status != PortalUserStatus.ACTIVE or not access or access.status != PortalAccessStatus.ACTIVE or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Invalid portal credentials")
    raw, csrf, session = await _create_session(db, user, request)
    await append_audit_event(db, organization_id=user.organization_id, action="portal.login", resource_type="client_portal_user", resource_id=str(user.id), outcome=AuditOutcome.SUCCESS, metadata={"email_hash": privacy_hash(user.email)})
    await db.commit(); return user, raw, csrf, session


async def authenticate(db: AsyncSession, raw_token: str) -> tuple[PortalActor, ClientPortalSession] | None:
    if not raw_token: return None
    session = await db.scalar(select(ClientPortalSession).where(ClientPortalSession.token_hash == token_hash(raw_token)))
    if not session or session.revoked_at is not None or _aware(session.expires_at) <= _now(): return None
    user = await db.get(ClientPortalUser, session.portal_user_id)
    if not user or user.status != PortalUserStatus.ACTIVE: return None
    access = await db.get(ClientPortalAccess, user.portal_access_id)
    if not access or access.status != PortalAccessStatus.ACTIVE: return None
    session.last_seen_at = _now(); await db.commit()
    return PortalActor(user.id, user.portal_access_id, user.organization_id, user.client_id, user.email), session


def csrf_valid(session: ClientPortalSession, value: str | None) -> bool:
    return bool(value and verify_token_hash(value, session.csrf_hash))


async def logout(db: AsyncSession, actor: PortalActor, session: ClientPortalSession) -> None:
    session.revoked_at = _now()
    await append_audit_event(db, organization_id=actor.organization_id, action="portal.logout", resource_type="client_portal_user", resource_id=str(actor.portal_user_id), outcome=AuditOutcome.SUCCESS)
    await db.commit()


async def create_share(db: AsyncSession, actor: ActorContext, payload: PortalShareCreate) -> ClientPortalShare:
    access = await _internal_access(db, actor, payload.portal_access_id)
    if payload.matter_id:
        link = await db.scalar(select(MatterClientLink).where(MatterClientLink.matter_id == payload.matter_id, MatterClientLink.client_id == access.client_id))
        if not link: raise HTTPException(422, "Matter is not linked to this portal client")
    if payload.share_type == PortalShareType.INVOICE:
        if not payload.resource_id: raise HTTPException(422, "Invoice share requires resource_id")
        invoice = await db.get(Invoice, payload.resource_id)
        if not invoice or invoice.organization_id != actor.organization_id or invoice.client_id != access.client_id: raise HTTPException(404, "Invoice not found")
        if invoice.status not in {InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID}: raise HTTPException(409, "Only issued invoices can be shared")
    elif payload.share_type == PortalShareType.DOCUMENT:
        if actor.role == OrganizationRole.BILLING: raise HTTPException(403, "Billing role cannot share legal documents")
        if not payload.resource_id: raise HTTPException(422, "Document share requires resource_id")
        document = await db.get(Document, payload.resource_id)
        if not document: raise HTTPException(404, "Document not found")
        link = await db.scalar(select(MatterClientLink).where(MatterClientLink.matter_id == document.matter_id, MatterClientLink.client_id == access.client_id))
        if not link: raise HTTPException(403, "Document matter is not linked to this client")
        decision = await decide_document_access(db, actor, document.id, required=DocumentAccessLevel.DOWNLOAD)
        if not decision.allowed: raise HTTPException(403, decision.reason)
        if payload.matter_id and payload.matter_id != document.matter_id: raise HTTPException(422, "Share matter does not match document matter")
        payload = payload.model_copy(update={"matter_id": document.matter_id})
    elif payload.share_type == PortalShareType.MATTER_UPDATE:
        if actor.role == OrganizationRole.BILLING: raise HTTPException(403, "Billing role cannot publish matter updates")
        if not payload.matter_id: raise HTTPException(422, "Matter update requires matter_id")
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    row = ClientPortalShare(
        organization_id=actor.organization_id, client_id=access.client_id, portal_access_id=access.id,
        matter_id=payload.matter_id, share_type=payload.share_type, resource_id=payload.resource_id,
        title=payload.title, message=payload.message, can_download=payload.can_download,
        shared_by_user_id=actor.user_id, shared_at=_now(), metadata_json=payload.metadata,
    )
    db.add(row); await db.flush()
    await append_audit_event(db, organization_id=actor.organization_id, actor=actor, action="portal.share.create", resource_type="client_portal_share", resource_id=str(row.id), outcome=AuditOutcome.SUCCESS, metadata={"share_type": row.share_type.value})
    await db.commit(); await db.refresh(row); return row


async def list_internal_shares(db: AsyncSession, actor: ActorContext, access_id: UUID) -> list[ClientPortalShare]:
    access = await _internal_access(db, actor, access_id)
    return list((await db.scalars(select(ClientPortalShare).where(ClientPortalShare.portal_access_id == access.id).order_by(ClientPortalShare.shared_at.desc()))).all())


async def create_request(db: AsyncSession, actor: ActorContext, payload: PortalRequestCreate) -> ClientPortalRequest:
    access = await _internal_access(db, actor, payload.portal_access_id)
    if actor.role == OrganizationRole.BILLING and payload.matter_id: raise HTTPException(403, "Billing role cannot create matter-linked client requests")
    if payload.matter_id:
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    row = ClientPortalRequest(organization_id=actor.organization_id, client_id=access.client_id, portal_access_id=access.id, matter_id=payload.matter_id, request_type=payload.request_type, title=payload.title, description=payload.description, due_at=payload.due_at, created_by_user_id=actor.user_id)
    db.add(row); await db.flush(); await append_audit_event(db, organization_id=actor.organization_id, actor=actor, action="portal.request.create", resource_type="client_portal_request", resource_id=str(row.id), outcome=AuditOutcome.SUCCESS)
    await db.commit(); await db.refresh(row); return row


async def firm_message(db: AsyncSession, actor: ActorContext, access_id: UUID, matter_id: UUID | None, body: str) -> ClientPortalMessage:
    access = await _internal_access(db, actor, access_id)
    if matter_id:
        decision = await decide_matter_access(db, actor, matter_id, required=MatterAccessLevel.VIEW)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    row = ClientPortalMessage(organization_id=actor.organization_id, client_id=access.client_id, portal_access_id=access.id, matter_id=matter_id, sender_type=PortalSenderType.FIRM, sender_user_id=actor.user_id, body=body, sent_at=_now())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def dashboard(db: AsyncSession, actor: PortalActor) -> dict:
    client = await db.get(Client, actor.client_id)
    if not client: raise HTTPException(404, "Client record not found")
    shares = list((await db.scalars(select(ClientPortalShare).where(ClientPortalShare.portal_access_id == actor.portal_access_id, ClientPortalShare.revoked_at.is_(None)).order_by(ClientPortalShare.shared_at.desc()).limit(100))).all())
    messages = list((await db.scalars(select(ClientPortalMessage).where(ClientPortalMessage.portal_access_id == actor.portal_access_id).order_by(ClientPortalMessage.sent_at.desc()).limit(100))).all())
    requests = list((await db.scalars(select(ClientPortalRequest).where(ClientPortalRequest.portal_access_id == actor.portal_access_id).order_by(ClientPortalRequest.created_at.desc()).limit(100))).all())
    invoice_ids = [s.resource_id for s in shares if s.share_type == PortalShareType.INVOICE and s.resource_id]
    invoices = list((await db.scalars(select(Invoice).where(Invoice.id.in_(invoice_ids)))).all()) if invoice_ids else []
    outstanding = sum((Decimal(str(i.amount_due)) for i in invoices if i.status in {InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID}), Decimal("0"))
    count = sum(1 for i in invoices if i.amount_due > 0)
    return {"client_id": actor.client_id, "client_name": client.display_name, "shares": shares, "messages": messages, "requests": requests, "outstanding_invoice_count": count, "outstanding_amount": f"{outstanding:.2f}"}


async def client_message(db: AsyncSession, actor: PortalActor, matter_id: UUID | None, body: str) -> ClientPortalMessage:
    if matter_id:
        shared = await db.scalar(select(func.count(ClientPortalShare.id)).where(ClientPortalShare.portal_access_id == actor.portal_access_id, ClientPortalShare.matter_id == matter_id, ClientPortalShare.revoked_at.is_(None)))
        if not shared: raise HTTPException(403, "Matter is not shared with this portal")
    row = ClientPortalMessage(organization_id=actor.organization_id, client_id=actor.client_id, portal_access_id=actor.portal_access_id, matter_id=matter_id, sender_type=PortalSenderType.CLIENT, body=body, sent_at=_now())
    db.add(row); await db.flush(); await append_audit_event(db, organization_id=actor.organization_id, action="portal.message.client", resource_type="client_portal_message", resource_id=str(row.id), outcome=AuditOutcome.SUCCESS, metadata={"portal_user_id": str(actor.portal_user_id)})
    await db.commit(); await db.refresh(row); return row


async def update_request(db: AsyncSession, actor: PortalActor, request_id: UUID, status: PortalRequestStatus) -> ClientPortalRequest:
    row = await db.get(ClientPortalRequest, request_id)
    if not row or row.portal_access_id != actor.portal_access_id: raise HTTPException(404, "Portal request not found")
    if status not in {PortalRequestStatus.IN_PROGRESS, PortalRequestStatus.COMPLETED}:
        raise HTTPException(422, "Client may only mark a request in progress or completed")
    row.status = status; row.completed_at = _now() if status == PortalRequestStatus.COMPLETED else None
    await db.commit(); await db.refresh(row); return row


async def get_share(db: AsyncSession, actor: PortalActor, share_id: UUID) -> ClientPortalShare:
    row = await db.get(ClientPortalShare, share_id)
    if not row or row.portal_access_id != actor.portal_access_id or row.revoked_at is not None: raise HTTPException(404, "Shared item not found")
    return row


async def invoice_snapshot_for_share(db: AsyncSession, actor: PortalActor, share_id: UUID) -> dict:
    share = await get_share(db, actor, share_id)
    if share.share_type != PortalShareType.INVOICE or not share.resource_id: raise HTTPException(422, "Shared item is not an invoice")
    invoice = await db.get(Invoice, share.resource_id)
    if not invoice or invoice.client_id != actor.client_id: raise HTTPException(404, "Invoice not found")
    version = await db.scalar(select(InvoiceVersion).where(InvoiceVersion.invoice_id == invoice.id).order_by(InvoiceVersion.version_number.desc()).limit(1))
    if not version: raise HTTPException(409, "Issued invoice snapshot is unavailable")
    return {"invoice_id": str(invoice.id), "status": invoice.status.value, "amount_due": str(invoice.amount_due), "amount_paid": str(invoice.amount_paid), "snapshot": version.snapshot_json, "content_hash": version.content_hash}


async def document_path_for_share(db: AsyncSession, actor: PortalActor, share_id: UUID):
    share = await get_share(db, actor, share_id)
    if share.share_type != PortalShareType.DOCUMENT or not share.resource_id or not share.can_download: raise HTTPException(403, "Document download is not permitted")
    document = await db.get(Document, share.resource_id)
    if not document or not document.storage_key: raise HTTPException(404, "Document file not found")
    return document, resolve_storage_key(document.storage_key)


async def list_client_approvals(db: AsyncSession, actor: PortalActor) -> list[ClientDocumentApprovalRequest]:
    return list((await db.scalars(select(ClientDocumentApprovalRequest).where(
        ClientDocumentApprovalRequest.portal_access_id == actor.portal_access_id,
        ClientDocumentApprovalRequest.status != ClientDocumentApprovalStatus.REVOKED,
    ).order_by(ClientDocumentApprovalRequest.created_at.desc()))).all())


async def respond_client_approval(db: AsyncSession, actor: PortalActor, approval_id: UUID, status: ClientDocumentApprovalStatus, note: str | None = None) -> ClientDocumentApprovalRequest:
    if status not in {ClientDocumentApprovalStatus.APPROVED, ClientDocumentApprovalStatus.CHANGES_REQUESTED, ClientDocumentApprovalStatus.DECLINED}:
        raise HTTPException(422, "Client may approve, request changes, or decline")
    row = await db.get(ClientDocumentApprovalRequest, approval_id)
    if not row or row.portal_access_id != actor.portal_access_id or row.client_id != actor.client_id:
        raise HTTPException(404, "Approval request not found")
    if row.status != ClientDocumentApprovalStatus.PENDING:
        raise HTTPException(409, "Approval request has already been answered or revoked")
    row.status = status
    row.response_note = note
    row.responded_by_portal_user_id = actor.portal_user_id
    row.responded_at = _now()
    await append_audit_event(db, organization_id=actor.organization_id, action="portal.document_approval.respond", resource_type="client_document_approval_request", resource_id=str(row.id), outcome=AuditOutcome.SUCCESS, metadata={"status": status.value, "portal_user_id": str(actor.portal_user_id)})
    await db.commit(); await db.refresh(row); return row
