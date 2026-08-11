from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class VersionSource(StrEnum):
    UPLOAD = "upload"
    SYSTEM = "system"
    REDLINE = "redline"
    SIGNED = "signed"


class CommentStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class ReviewRequestStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"




class ClientDocumentApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    DECLINED = "declined"
    REVOKED = "revoked"


class ESignatureProvider(StrEnum):
    MANUAL = "manual"
    MOCK = "mock"
    DOCUSIGN = "docusign"
    ADOBE_SIGN = "adobe_sign"
    OTHER = "other"


class ESignatureEnvelopeStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    COMPLETED = "completed"
    DECLINED = "declined"
    VOIDED = "voided"


class ESignatureSignerStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    VIEWED = "viewed"
    SIGNED = "signed"
    DECLINED = "declined"


class DocumentVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_document_version_number"),)

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    source: Mapped[VersionSource] = mapped_column(Enum(VersionSource, native_enum=False), default=VersionSource.UPLOAD, index=True)
    filename: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str] = mapped_column(String(1000))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    change_note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)


class DocumentComment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_comments"

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    document_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    parent_comment_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_comments.id", ondelete="CASCADE"), nullable=True, index=True)
    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("security_users.id", ondelete="RESTRICT"), index=True)
    body: Mapped[str] = mapped_column(Text)
    anchor_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[CommentStatus] = mapped_column(Enum(CommentStatus, native_enum=False), default=CommentStatus.OPEN, index=True)
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentReviewRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_review_requests"

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    document_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("security_users.id", ondelete="RESTRICT"), index=True)
    assigned_to_membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="RESTRICT"), index=True)
    status: Mapped[ReviewRequestStatus] = mapped_column(Enum(ReviewRequestStatus, native_enum=False), default=ReviewRequestStatus.OPEN, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentApproval(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_approvals"

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    document_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    review_request_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_review_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("security_users.id", ondelete="RESTRICT"), index=True)
    decision: Mapped[ApprovalDecision] = mapped_column(Enum(ApprovalDecision, native_enum=False), index=True)
    comment: Mapped[str | None] = mapped_column(Text)


class ESignatureEnvelope(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "esignature_envelopes"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    document_version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"), index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    provider: Mapped[ESignatureProvider] = mapped_column(Enum(ESignatureProvider, native_enum=False), default=ESignatureProvider.MANUAL, index=True)
    status: Mapped[ESignatureEnvelopeStatus] = mapped_column(Enum(ESignatureEnvelopeStatus, native_enum=False), default=ESignatureEnvelopeStatus.DRAFT, index=True)
    title: Mapped[str] = mapped_column(String(300))
    provider_reference: Mapped[str | None] = mapped_column(String(220), index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ESignatureSigner(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "esignature_signers"

    envelope_id: Mapped[UUID] = mapped_column(ForeignKey("esignature_envelopes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(220))
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str | None] = mapped_column(String(120))
    signing_order: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ESignatureSignerStatus] = mapped_column(Enum(ESignatureSignerStatus, native_enum=False), default=ESignatureSignerStatus.PENDING, index=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClientDocumentApprovalRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_document_approval_requests"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    portal_access_id: Mapped[UUID] = mapped_column(ForeignKey("client_portal_access.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    document_version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ClientDocumentApprovalStatus] = mapped_column(Enum(ClientDocumentApprovalStatus, native_enum=False), default=ClientDocumentApprovalStatus.PENDING, index=True)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    responded_by_portal_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("client_portal_users.id", ondelete="SET NULL"), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_note: Mapped[str | None] = mapped_column(Text)
