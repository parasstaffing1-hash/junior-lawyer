from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.collaboration import (
    ApprovalDecision, ClientDocumentApprovalStatus, CommentStatus, ESignatureEnvelopeStatus, ESignatureProvider,
    ESignatureSignerStatus, ReviewRequestStatus, VersionSource,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DocumentVersionCreate(BaseModel):
    change_note: str | None = None
    source: VersionSource = VersionSource.UPLOAD


class DocumentVersionRead(ORMModel):
    id: UUID
    document_id: UUID
    matter_id: UUID
    version_number: int
    source: VersionSource
    filename: str
    sha256: str
    size_bytes: int
    change_note: str | None
    created_by_user_id: UUID | None
    created_at: datetime


class CommentCreate(BaseModel):
    document_version_id: UUID | None = None
    parent_comment_id: UUID | None = None
    body: str = Field(min_length=1)
    anchor: dict = Field(default_factory=dict)


class CommentRead(ORMModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID | None
    matter_id: UUID
    parent_comment_id: UUID | None
    author_user_id: UUID
    body: str
    anchor_json: dict
    status: CommentStatus
    resolved_by_user_id: UUID | None
    resolved_at: datetime | None
    created_at: datetime


class ReviewRequestCreate(BaseModel):
    document_version_id: UUID | None = None
    assigned_to_membership_id: UUID
    due_at: datetime | None = None
    note: str | None = None


class ReviewRequestRead(ORMModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID | None
    matter_id: UUID
    requested_by_user_id: UUID
    assigned_to_membership_id: UUID
    status: ReviewRequestStatus
    due_at: datetime | None
    note: str | None
    completed_at: datetime | None
    created_at: datetime


class ApprovalCreate(BaseModel):
    document_version_id: UUID | None = None
    review_request_id: UUID | None = None
    decision: ApprovalDecision
    comment: str | None = None


class ApprovalRead(ORMModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID | None
    review_request_id: UUID | None
    matter_id: UUID
    reviewer_user_id: UUID
    decision: ApprovalDecision
    comment: str | None
    created_at: datetime


class SignerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=220)
    email: str = Field(min_length=3, max_length=320)
    role: str | None = None
    signing_order: int = Field(default=1, ge=1, le=50)


class EnvelopeCreate(BaseModel):
    document_version_id: UUID
    provider: ESignatureProvider = ESignatureProvider.MANUAL
    title: str = Field(min_length=2, max_length=300)
    signers: list[SignerCreate] = Field(min_length=1)
    metadata: dict = Field(default_factory=dict)


class SignerRead(ORMModel):
    id: UUID
    envelope_id: UUID
    name: str
    email: str
    role: str | None
    signing_order: int
    status: ESignatureSignerStatus
    signed_at: datetime | None


class EnvelopeRead(ORMModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID
    matter_id: UUID
    provider: ESignatureProvider
    status: ESignatureEnvelopeStatus
    title: str
    provider_reference: str | None
    sent_at: datetime | None
    completed_at: datetime | None
    metadata_json: dict
    created_at: datetime
    signers: list[SignerRead] = Field(default_factory=list)


class ClientApprovalRequestCreate(BaseModel):
    portal_access_id: UUID
    document_version_id: UUID
    title: str = Field(min_length=2, max_length=300)
    message: str | None = None


class ClientApprovalRead(ORMModel):
    id: UUID
    portal_access_id: UUID
    client_id: UUID
    matter_id: UUID
    document_id: UUID
    document_version_id: UUID
    title: str
    message: str | None
    status: ClientDocumentApprovalStatus
    responded_at: datetime | None
    response_note: str | None
    created_at: datetime


class ClientApprovalDecision(BaseModel):
    status: ClientDocumentApprovalStatus
    note: str | None = None
