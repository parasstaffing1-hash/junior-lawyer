from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PortalUserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class PortalShareType(StrEnum):
    DOCUMENT = "document"
    INVOICE = "invoice"
    MATTER_UPDATE = "matter_update"


class PortalSenderType(StrEnum):
    FIRM = "firm"
    CLIENT = "client"


class PortalRequestStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ClientPortalUser(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_portal_users"
    __table_args__ = (
        UniqueConstraint("portal_access_id", name="uq_portal_user_access"),
        UniqueConstraint("organization_id", "email", name="uq_portal_user_org_email"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    portal_access_id: Mapped[UUID] = mapped_column(ForeignKey("client_portal_access.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[PortalUserStatus] = mapped_column(Enum(PortalUserStatus, native_enum=False), default=PortalUserStatus.ACTIVE, index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClientPortalSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_portal_sessions"

    portal_user_id: Mapped[UUID] = mapped_column(ForeignKey("client_portal_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent_hash: Mapped[str | None] = mapped_column(String(64))


class ClientPortalShare(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_portal_shares"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    portal_access_id: Mapped[UUID] = mapped_column(ForeignKey("client_portal_access.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    share_type: Mapped[PortalShareType] = mapped_column(Enum(PortalShareType, native_enum=False), index=True)
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str | None] = mapped_column(Text)
    can_download: Mapped[bool] = mapped_column(Boolean, default=False)
    shared_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    shared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ClientPortalMessage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_portal_messages"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    portal_access_id: Mapped[UUID] = mapped_column(ForeignKey("client_portal_access.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    sender_type: Mapped[PortalSenderType] = mapped_column(Enum(PortalSenderType, native_enum=False), index=True)
    sender_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClientPortalRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_portal_requests"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    portal_access_id: Mapped[UUID] = mapped_column(ForeignKey("client_portal_access.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    request_type: Mapped[str] = mapped_column(String(80), default="information", index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PortalRequestStatus] = mapped_column(Enum(PortalRequestStatus, native_enum=False), default=PortalRequestStatus.OPEN, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
