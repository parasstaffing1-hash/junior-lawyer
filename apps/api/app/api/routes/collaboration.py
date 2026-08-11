from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.collaboration import (
    ApprovalCreate, ApprovalRead, ClientApprovalRead, ClientApprovalRequestCreate, CommentCreate, CommentRead, DocumentVersionRead,
    EnvelopeCreate, EnvelopeRead, ReviewRequestCreate, ReviewRequestRead, SignerRead,
)
from app.services.collaboration import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/collaboration", tags=["collaboration"])


@router.get("/documents/{document_id}/versions", response_model=list[DocumentVersionRead])
async def versions(document_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [DocumentVersionRead.model_validate(r) for r in await service.list_versions(db, actor, document_id)]


@router.post("/documents/{document_id}/versions/snapshot", response_model=DocumentVersionRead, status_code=201)
async def snapshot(document_id: UUID, change_note: str | None = None, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return DocumentVersionRead.model_validate(await service.snapshot_current(db, actor, document_id, change_note))


@router.post("/documents/{document_id}/versions", response_model=DocumentVersionRead, status_code=201)
async def upload_version(document_id: UUID, file: UploadFile = File(...), change_note: str | None = Form(default=None), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return DocumentVersionRead.model_validate(await service.upload_version(db, actor, document_id, file, change_note))


@router.get("/versions/{version_id}/download")
async def download_version(version_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row, path = await service.version_file(db, actor, version_id)
    return FileResponse(path=path, filename=row.filename, media_type="application/octet-stream")


@router.get("/documents/{document_id}/comments", response_model=list[CommentRead])
async def comments(document_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [CommentRead.model_validate(r) for r in await service.list_comments(db, actor, document_id)]


@router.post("/documents/{document_id}/comments", response_model=CommentRead, status_code=201)
async def add_comment(document_id: UUID, payload: CommentCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return CommentRead.model_validate(await service.add_comment(db, actor, document_id, payload))


@router.post("/comments/{comment_id}/resolve", response_model=CommentRead)
async def resolve_comment(comment_id: UUID, resolved: bool = True, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return CommentRead.model_validate(await service.resolve_comment(db, actor, comment_id, resolved))


@router.get("/documents/{document_id}/reviews", response_model=list[ReviewRequestRead])
async def reviews(document_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ReviewRequestRead.model_validate(r) for r in await service.list_review_requests(db, actor, document_id)]


@router.post("/documents/{document_id}/reviews", response_model=ReviewRequestRead, status_code=201)
async def create_review(document_id: UUID, payload: ReviewRequestCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ReviewRequestRead.model_validate(await service.create_review_request(db, actor, document_id, payload))


@router.post("/documents/{document_id}/approvals", response_model=ApprovalRead, status_code=201)
async def approval(document_id: UUID, payload: ApprovalCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ApprovalRead.model_validate(await service.record_approval(db, actor, document_id, payload))


@router.post("/documents/{document_id}/esign", response_model=EnvelopeRead, status_code=201)
async def create_envelope(document_id: UUID, payload: EnvelopeCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row, signers = await service.create_envelope(db, actor, document_id, payload)
    return EnvelopeRead(**{**EnvelopeRead.model_validate(row).model_dump(), "signers": [SignerRead.model_validate(s) for s in signers]})


@router.get("/esign/{envelope_id}", response_model=EnvelopeRead)
async def envelope(envelope_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row, signers = await service.get_envelope(db, actor, envelope_id)
    return EnvelopeRead(**{**EnvelopeRead.model_validate(row).model_dump(), "signers": [SignerRead.model_validate(s) for s in signers]})


@router.post("/esign/{envelope_id}/send", response_model=EnvelopeRead)
async def send_envelope(envelope_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    await service.send_envelope(db, actor, envelope_id)
    row, signers = await service.get_envelope(db, actor, envelope_id)
    return EnvelopeRead(**{**EnvelopeRead.model_validate(row).model_dump(), "signers": [SignerRead.model_validate(s) for s in signers]})


@router.post("/esign/signers/{signer_id}/mark-signed", response_model=SignerRead)
async def mark_signed(signer_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SignerRead.model_validate(await service.mark_signer_signed(db, actor, signer_id))


@router.get("/documents/{document_id}/client-approvals", response_model=list[ClientApprovalRead])
async def client_approvals(document_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ClientApprovalRead.model_validate(r) for r in await service.list_client_approval_requests(db, actor, document_id)]


@router.post("/documents/{document_id}/client-approvals", response_model=ClientApprovalRead, status_code=201)
async def request_client_approval(document_id: UUID, payload: ClientApprovalRequestCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientApprovalRead.model_validate(await service.create_client_approval_request(db, actor, document_id, payload))
