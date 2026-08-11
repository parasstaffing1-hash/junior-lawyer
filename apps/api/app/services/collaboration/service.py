from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.collaboration import (
    ApprovalDecision, ClientDocumentApprovalRequest, ClientDocumentApprovalStatus, CommentStatus, DocumentApproval, DocumentComment, DocumentReviewRequest,
    DocumentVersion, ESignatureEnvelope, ESignatureEnvelopeStatus, ESignatureProvider,
    ESignatureSigner, ESignatureSignerStatus, ReviewRequestStatus, VersionSource,
)
from app.models.document import Document
from app.models.crm import ClientPortalAccess, MatterClientLink, PortalAccessStatus
from app.models.security import AuditOutcome, DocumentAccessLevel, MatterAccessLevel, OrganizationMembership
from app.schemas.collaboration import ApprovalCreate, ClientApprovalRequestCreate, CommentCreate, EnvelopeCreate, ReviewRequestCreate
from app.services.documents.storage import discard_staged, resolve_storage_key, stage_upload
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext
from app.services.security.permissions import decide_document_access, decide_matter_access


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _audit(db: AsyncSession, actor: ActorContext, action: str, resource_type: str, resource_id: UUID | str, metadata: dict | None = None) -> None:
    await append_audit_event(db, organization_id=actor.organization_id, actor=actor, action=action,
        resource_type=resource_type, resource_id=str(resource_id), outcome=AuditOutcome.SUCCESS, metadata=metadata or {})


async def _document(db: AsyncSession, actor: ActorContext, document_id: UUID, *, edit: bool = False) -> Document:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    decision = await decide_document_access(db, actor, document_id, required=DocumentAccessLevel.EDIT if edit else DocumentAccessLevel.VIEW)
    if not decision.allowed:
        raise HTTPException(403, decision.reason)
    return document


async def _next_version(db: AsyncSession, document_id: UUID) -> int:
    return int(await db.scalar(select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(DocumentVersion.document_id == document_id)) or 0) + 1


def _version_path(document: Document, version_number: int, filename: str) -> tuple[Path, str]:
    relative = Path(str(document.matter_id)) / str(document.id) / "versions" / f"v{version_number:04d}" / filename
    root = settings.storage_root.resolve()
    destination = (settings.storage_root / relative).resolve()
    if root not in destination.parents:
        raise RuntimeError("Refusing to write outside document storage root")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination, relative.as_posix()


async def snapshot_current(db: AsyncSession, actor: ActorContext, document_id: UUID, change_note: str | None = None) -> DocumentVersion:
    document = await _document(db, actor, document_id, edit=True)
    if not document.storage_key or not document.sha256:
        raise HTTPException(409, "Document has no stored original to snapshot")
    source = resolve_storage_key(document.storage_key)
    if not source.exists():
        raise HTTPException(410, "Stored document file is missing")
    number = await _next_version(db, document.id)
    destination, storage_key = _version_path(document, number, document.filename)
    shutil.copy2(source, destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    row = DocumentVersion(document_id=document.id, matter_id=document.matter_id, version_number=number,
        source=VersionSource.SYSTEM, filename=document.filename, storage_key=storage_key, sha256=digest,
        size_bytes=destination.stat().st_size, change_note=change_note or "Snapshot of current document",
        created_by_user_id=actor.user_id)
    db.add(row); await db.flush(); await _audit(db, actor, "collaboration.version.snapshot", "document_version", row.id)
    await db.commit(); await db.refresh(row); return row


async def upload_version(db: AsyncSession, actor: ActorContext, document_id: UUID, upload: UploadFile, change_note: str | None = None) -> DocumentVersion:
    document = await _document(db, actor, document_id, edit=True)
    staged = await stage_upload(upload)
    try:
        number = await _next_version(db, document.id)
        destination, storage_key = _version_path(document, number, staged.safe_filename)
        shutil.move(str(staged.path), destination)
        row = DocumentVersion(document_id=document.id, matter_id=document.matter_id, version_number=number,
            source=VersionSource.UPLOAD, filename=staged.safe_filename, storage_key=storage_key, sha256=staged.sha256,
            size_bytes=staged.size_bytes, change_note=change_note, created_by_user_id=actor.user_id)
        db.add(row); await db.flush(); await _audit(db, actor, "collaboration.version.upload", "document_version", row.id, {"sha256": staged.sha256})
        await db.commit(); await db.refresh(row); return row
    finally:
        if staged.path.exists(): discard_staged(staged)


async def list_versions(db: AsyncSession, actor: ActorContext, document_id: UUID) -> list[DocumentVersion]:
    await _document(db, actor, document_id)
    return list((await db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == document_id).order_by(DocumentVersion.version_number.desc()))).all())


async def version_file(db: AsyncSession, actor: ActorContext, version_id: UUID) -> tuple[DocumentVersion, Path]:
    row = await db.get(DocumentVersion, version_id)
    if not row: raise HTTPException(404, "Document version not found")
    await _document(db, actor, row.document_id)
    path=(settings.storage_root / row.storage_key).resolve(); root=settings.storage_root.resolve()
    if root not in path.parents or not path.exists(): raise HTTPException(410, "Version file is unavailable")
    return row, path


async def add_comment(db: AsyncSession, actor: ActorContext, document_id: UUID, payload: CommentCreate) -> DocumentComment:
    document = await _document(db, actor, document_id, edit=True)
    if payload.document_version_id:
        version=await db.get(DocumentVersion,payload.document_version_id)
        if not version or version.document_id != document.id: raise HTTPException(422,"Version does not belong to this document")
    if payload.parent_comment_id:
        parent=await db.get(DocumentComment,payload.parent_comment_id)
        if not parent or parent.document_id != document.id: raise HTTPException(422,"Parent comment does not belong to this document")
    row=DocumentComment(document_id=document.id,document_version_id=payload.document_version_id,matter_id=document.matter_id,
        parent_comment_id=payload.parent_comment_id,author_user_id=actor.user_id,body=payload.body,anchor_json=payload.anchor)
    db.add(row); await db.flush(); await _audit(db,actor,"collaboration.comment.create","document_comment",row.id)
    await db.commit(); await db.refresh(row); return row


async def list_comments(db: AsyncSession, actor: ActorContext, document_id: UUID) -> list[DocumentComment]:
    await _document(db,actor,document_id)
    return list((await db.scalars(select(DocumentComment).where(DocumentComment.document_id==document_id).order_by(DocumentComment.created_at))).all())


async def resolve_comment(db: AsyncSession, actor: ActorContext, comment_id: UUID, resolved: bool) -> DocumentComment:
    row=await db.get(DocumentComment,comment_id)
    if not row: raise HTTPException(404,"Comment not found")
    await _document(db,actor,row.document_id,edit=True)
    row.status=CommentStatus.RESOLVED if resolved else CommentStatus.OPEN
    row.resolved_by_user_id=actor.user_id if resolved else None; row.resolved_at=_now() if resolved else None
    await _audit(db,actor,"collaboration.comment.resolve","document_comment",row.id,{"resolved":resolved})
    await db.commit(); await db.refresh(row); return row


async def create_review_request(db: AsyncSession, actor: ActorContext, document_id: UUID, payload: ReviewRequestCreate) -> DocumentReviewRequest:
    document=await _document(db,actor,document_id,edit=True)
    membership=await db.get(OrganizationMembership,payload.assigned_to_membership_id)
    if not membership or membership.organization_id != actor.organization_id: raise HTTPException(422,"Reviewer membership is not in this organization")
    if payload.document_version_id:
        version=await db.get(DocumentVersion,payload.document_version_id)
        if not version or version.document_id!=document.id: raise HTTPException(422,"Version does not belong to this document")
    row=DocumentReviewRequest(document_id=document.id,document_version_id=payload.document_version_id,matter_id=document.matter_id,
        requested_by_user_id=actor.user_id,assigned_to_membership_id=payload.assigned_to_membership_id,due_at=payload.due_at,note=payload.note)
    db.add(row); await db.flush(); await _audit(db,actor,"collaboration.review.request","document_review_request",row.id)
    await db.commit(); await db.refresh(row); return row


async def list_review_requests(db: AsyncSession, actor: ActorContext, document_id: UUID) -> list[DocumentReviewRequest]:
    await _document(db,actor,document_id)
    return list((await db.scalars(select(DocumentReviewRequest).where(DocumentReviewRequest.document_id==document_id).order_by(DocumentReviewRequest.created_at.desc()))).all())


async def record_approval(db: AsyncSession, actor: ActorContext, document_id: UUID, payload: ApprovalCreate) -> DocumentApproval:
    document=await _document(db,actor,document_id,edit=True)
    if payload.review_request_id:
        request=await db.get(DocumentReviewRequest,payload.review_request_id)
        if not request or request.document_id!=document.id: raise HTTPException(422,"Review request does not belong to this document")
        if request.assigned_to_membership_id != actor.membership_id: raise HTTPException(403,"Only the assigned reviewer can decide this request")
        request.status = ReviewRequestStatus.APPROVED if payload.decision==ApprovalDecision.APPROVED else ReviewRequestStatus.CHANGES_REQUESTED
        request.completed_at=_now()
    row=DocumentApproval(document_id=document.id,document_version_id=payload.document_version_id,review_request_id=payload.review_request_id,
        matter_id=document.matter_id,reviewer_user_id=actor.user_id,decision=payload.decision,comment=payload.comment)
    db.add(row); await db.flush(); await _audit(db,actor,"collaboration.approval.record","document_approval",row.id,{"decision":payload.decision.value})
    await db.commit(); await db.refresh(row); return row


async def create_envelope(db: AsyncSession, actor: ActorContext, document_id: UUID, payload: EnvelopeCreate) -> tuple[ESignatureEnvelope,list[ESignatureSigner]]:
    document=await _document(db,actor,document_id,edit=True)
    version=await db.get(DocumentVersion,payload.document_version_id)
    if not version or version.document_id != document.id: raise HTTPException(422,"Version does not belong to this document")
    if payload.provider not in {ESignatureProvider.MANUAL, ESignatureProvider.MOCK}:
        raise HTTPException(501,"External e-sign provider connector is not configured in this foundation")
    row=ESignatureEnvelope(organization_id=actor.organization_id,document_id=document.id,document_version_id=version.id,
        matter_id=document.matter_id,provider=payload.provider,title=payload.title,created_by_user_id=actor.user_id,metadata_json=payload.metadata)
    db.add(row); await db.flush()
    signers=[]
    for signer in sorted(payload.signers,key=lambda s:s.signing_order):
        item=ESignatureSigner(envelope_id=row.id,**signer.model_dump()); db.add(item); signers.append(item)
    await db.flush(); await _audit(db,actor,"collaboration.esign.create","esignature_envelope",row.id,{"provider":payload.provider.value})
    await db.commit(); await db.refresh(row)
    for signer in signers: await db.refresh(signer)
    return row,signers


async def send_envelope(db: AsyncSession, actor: ActorContext, envelope_id: UUID) -> ESignatureEnvelope:
    row=await db.get(ESignatureEnvelope,envelope_id)
    if not row or row.organization_id!=actor.organization_id: raise HTTPException(404,"Envelope not found")
    decision=await decide_matter_access(db,actor,row.matter_id,required=MatterAccessLevel.WORK)
    if not decision.allowed: raise HTTPException(403,decision.reason)
    if row.status!=ESignatureEnvelopeStatus.DRAFT: raise HTTPException(409,"Envelope is not in draft state")
    row.status=ESignatureEnvelopeStatus.SENT; row.sent_at=_now(); row.provider_reference=f"{row.provider.value}-{row.id}"
    for signer in (await db.scalars(select(ESignatureSigner).where(ESignatureSigner.envelope_id==row.id))).all(): signer.status=ESignatureSignerStatus.SENT
    await _audit(db,actor,"collaboration.esign.send","esignature_envelope",row.id)
    await db.commit(); await db.refresh(row); return row


async def mark_signer_signed(db: AsyncSession, actor: ActorContext, signer_id: UUID) -> ESignatureSigner:
    signer=await db.get(ESignatureSigner,signer_id)
    if not signer: raise HTTPException(404,"Signer not found")
    envelope=await db.get(ESignatureEnvelope,signer.envelope_id)
    if not envelope or envelope.organization_id!=actor.organization_id: raise HTTPException(404,"Envelope not found")
    decision=await decide_matter_access(db,actor,envelope.matter_id,required=MatterAccessLevel.WORK)
    if not decision.allowed: raise HTTPException(403,decision.reason)
    # Manual/mock completion records workflow state only; it is not a cryptographic signature service.
    signer.status=ESignatureSignerStatus.SIGNED; signer.signed_at=_now()
    await db.flush()
    remaining=await db.scalar(select(func.count(ESignatureSigner.id)).where(ESignatureSigner.envelope_id==envelope.id,ESignatureSigner.status!=ESignatureSignerStatus.SIGNED)) or 0
    if remaining==0: envelope.status=ESignatureEnvelopeStatus.COMPLETED; envelope.completed_at=_now()
    await _audit(db,actor,"collaboration.esign.signer_marked","esignature_signer",signer.id)
    await db.commit(); await db.refresh(signer); return signer


async def get_envelope(db: AsyncSession, actor: ActorContext, envelope_id: UUID) -> tuple[ESignatureEnvelope,list[ESignatureSigner]]:
    row=await db.get(ESignatureEnvelope,envelope_id)
    if not row or row.organization_id!=actor.organization_id: raise HTTPException(404,"Envelope not found")
    decision=await decide_matter_access(db,actor,row.matter_id)
    if not decision.allowed: raise HTTPException(403,decision.reason)
    signers=list((await db.scalars(select(ESignatureSigner).where(ESignatureSigner.envelope_id==row.id).order_by(ESignatureSigner.signing_order))).all())
    return row,signers


async def create_client_approval_request(db: AsyncSession, actor: ActorContext, document_id: UUID, payload: ClientApprovalRequestCreate) -> ClientDocumentApprovalRequest:
    document = await _document(db, actor, document_id, edit=True)
    version = await db.get(DocumentVersion, payload.document_version_id)
    if not version or version.document_id != document.id:
        raise HTTPException(422, "Version does not belong to this document")
    access = await db.get(ClientPortalAccess, payload.portal_access_id)
    if not access or access.organization_id != actor.organization_id or access.status == PortalAccessStatus.REVOKED:
        raise HTTPException(404, "Portal access not found")
    link = await db.scalar(select(MatterClientLink).where(MatterClientLink.matter_id == document.matter_id, MatterClientLink.client_id == access.client_id))
    if not link:
        raise HTTPException(422, "This portal client is not linked to the document matter")
    row = ClientDocumentApprovalRequest(organization_id=actor.organization_id, portal_access_id=access.id, client_id=access.client_id,
        matter_id=document.matter_id, document_id=document.id, document_version_id=version.id, title=payload.title, message=payload.message,
        status=ClientDocumentApprovalStatus.PENDING, requested_by_user_id=actor.user_id)
    db.add(row); await db.flush(); await _audit(db, actor, "collaboration.client_approval.request", "client_document_approval_request", row.id)
    await db.commit(); await db.refresh(row); return row


async def list_client_approval_requests(db: AsyncSession, actor: ActorContext, document_id: UUID) -> list[ClientDocumentApprovalRequest]:
    await _document(db, actor, document_id)
    return list((await db.scalars(select(ClientDocumentApprovalRequest).where(ClientDocumentApprovalRequest.document_id == document_id).order_by(ClientDocumentApprovalRequest.created_at.desc()))).all())
