from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"


class OrganizationRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    PARTNER = "partner"
    LAWYER = "lawyer"
    JUNIOR = "junior"
    PARALEGAL = "paralegal"
    BILLING = "billing"
    READ_ONLY = "read_only"


class MatterAccessLevel(StrEnum):
    VIEW = "view"
    WORK = "work"
    MANAGE = "manage"


class DocumentAccessLevel(StrEnum):
    VIEW = "view"
    DOWNLOAD = "download"
    EDIT = "edit"


class AccessEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class ConfidentialityLevel(StrEnum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    HIGHLY_CONFIDENTIAL = "highly_confidential"
    ETHICAL_WALL = "ethical_wall"


class MatterAccessMode(StrEnum):
    ORGANIZATION = "organization"
    EXPLICIT = "explicit"


class PolicyDecision(StrEnum):
    INHERIT = "inherit"
    ALLOW = "allow"
    DENY = "deny"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    ALLOWED = "allowed"
    DENIED = "denied"


class RetentionResourceType(StrEnum):
    MATTER = "matter"
    DOCUMENT = "document"
    AI_RUN = "ai_run"
    DRAFT = "draft"
    CONTRACT = "contract"
    AUDIT = "audit"


class DeletionStatus(StrEnum):
    REQUESTED = "requested"
    BLOCKED = "blocked"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    EXECUTED = "executed"


class LegalHoldStatus(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class Organization(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(250), index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, native_enum=False),
        default=OrganizationStatus.ACTIVE,
        index=True,
    )
    default_language: Mapped[str] = mapped_column(String(20), default="bilingual")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    memberships = relationship("OrganizationMembership", back_populates="organization", lazy="selectin")
    security_policy = relationship(
        "OrganizationSecurityPolicy",
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SecurityUser(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "security_users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(250))
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False), default=UserStatus.ACTIVE, index=True
    )
    locale: Mapped[str] = mapped_column(String(20), default="en")
    # E.164, for WhatsApp diary reminders. Optional: a lawyer who wants only
    # email never provides one.
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_version: Mapped[int] = mapped_column(Integer, default=1)

    memberships = relationship(
        "OrganizationMembership",
        back_populates="user",
        foreign_keys="OrganizationMembership.user_id",
        lazy="selectin",
    )
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan", lazy="selectin")


class OrganizationMembership(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("security_users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole, native_enum=False), default=OrganizationRole.LAWYER, index=True
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, native_enum=False), default=MembershipStatus.ACTIVE, index=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    invited_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True
    )

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("SecurityUser", foreign_keys=[user_id], back_populates="memberships")


class OrganizationSecurityPolicy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organization_security_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_security_policy_organization"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    session_idle_timeout_minutes: Mapped[int] = mapped_column(Integer, default=480)
    session_absolute_lifetime_hours: Mapped[int] = mapped_column(Integer, default=24)
    max_concurrent_sessions: Mapped[int] = mapped_column(Integer, default=5)
    password_min_length: Mapped[int] = mapped_column(Integer, default=12)
    max_failed_login_attempts: Mapped[int] = mapped_column(Integer, default=5)
    lockout_minutes: Mapped[int] = mapped_column(Integer, default=15)
    allow_remote_ai_default: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_exports_default: Mapped[bool] = mapped_column(Boolean, default=True)
    require_mfa_for_remote_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    require_mfa_for_highly_confidential: Mapped[bool] = mapped_column(Boolean, default=False)
    audit_log_retention_days: Mapped[int] = mapped_column(Integer, default=2555)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    organization = relationship("Organization", back_populates="security_policy")


class UserMFACredential(Base, UUIDMixin, TimestampMixin):
    """A user's enrolled authenticator.

    The row exists from the moment enrolment starts; `confirmed_at` is what
    makes it binding, so an abandoned enrolment can never lock anyone out.
    """

    __tablename__ = "user_mfa_credentials"
    __table_args__ = (UniqueConstraint("user_id", name="uq_mfa_credential_user"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("security_users.id", ondelete="CASCADE"), index=True
    )
    secret: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(120), default="Authenticator app")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Highest TOTP counter already spent, so a code cannot be replayed inside
    # the window it was issued for.
    last_used_counter: Mapped[int | None] = mapped_column(Integer)

    user = relationship("SecurityUser", lazy="selectin")


class UserRecoveryCode(Base, UUIDMixin, TimestampMixin):
    """Single-use fallback for a lost authenticator. Stored hashed, never raw."""

    __tablename__ = "user_recovery_codes"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("security_users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("security_users.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    password_version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(300))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent_hash: Mapped[str | None] = mapped_column(String(64))
    auth_method: Mapped[str] = mapped_column(String(40), default="password")

    user = relationship("SecurityUser", back_populates="sessions")
    membership = relationship("OrganizationMembership", lazy="selectin")


class MatterSecurityProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_security_profiles"
    __table_args__ = (UniqueConstraint("matter_id", name="uq_matter_security_profile_matter"),)

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    classification: Mapped[ConfidentialityLevel] = mapped_column(
        Enum(ConfidentialityLevel, native_enum=False),
        default=ConfidentialityLevel.CONFIDENTIAL,
        index=True,
    )
    access_mode: Mapped[MatterAccessMode] = mapped_column(
        Enum(MatterAccessMode, native_enum=False),
        default=MatterAccessMode.ORGANIZATION,
        index=True,
    )
    remote_ai_policy: Mapped[PolicyDecision] = mapped_column(
        Enum(PolicyDecision, native_enum=False), default=PolicyDecision.INHERIT, index=True
    )
    export_policy: Mapped[PolicyDecision] = mapped_column(
        Enum(PolicyDecision, native_enum=False), default=PolicyDecision.INHERIT, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True
    )


class MatterAccessGrant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_access_grants"
    __table_args__ = (
        UniqueConstraint("matter_id", "membership_id", name="uq_matter_grant_membership"),
    )

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True
    )
    effect: Mapped[AccessEffect] = mapped_column(
        Enum(AccessEffect, native_enum=False), default=AccessEffect.ALLOW, index=True
    )
    access_level: Mapped[MatterAccessLevel] = mapped_column(
        Enum(MatterAccessLevel, native_enum=False), default=MatterAccessLevel.VIEW, index=True
    )
    allow_remote_ai: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allow_export: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    granted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reason: Mapped[str | None] = mapped_column(String(500))


class DocumentAccessGrant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_access_grants"
    __table_args__ = (
        UniqueConstraint("document_id", "membership_id", name="uq_document_grant_membership"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True
    )
    effect: Mapped[AccessEffect] = mapped_column(
        Enum(AccessEffect, native_enum=False), default=AccessEffect.ALLOW, index=True
    )
    access_level: Mapped[DocumentAccessLevel] = mapped_column(
        Enum(DocumentAccessLevel, native_enum=False), default=DocumentAccessLevel.VIEW, index=True
    )
    granted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reason: Mapped[str | None] = mapped_column(String(500))


class AuditChainHead(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_chain_heads"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_audit_chain_head_org"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    head_hash: Mapped[str] = mapped_column(String(64), default="0" * 64)


class SecurityAuditEntry(Base, UUIDMixin):
    __tablename__ = "security_audit_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "sequence", name="uq_audit_org_sequence"),
        UniqueConstraint("event_hash", name="uq_audit_event_hash"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_membership_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(160), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), index=True)
    outcome: Mapped[AuditOutcome] = mapped_column(
        Enum(AuditOutcome, native_enum=False), index=True
    )
    reason: Mapped[str | None] = mapped_column(String(700))
    request_id: Mapped[str | None] = mapped_column(String(120), index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent_hash: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), index=True)
    signature_mode: Mapped[str] = mapped_column(String(40), default="sha256-chain")


class RetentionPolicy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "retention_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "resource_type", name="uq_retention_org_resource"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    resource_type: Mapped[RetentionResourceType] = mapped_column(
        Enum(RetentionResourceType, native_enum=False), index=True
    )
    retention_days: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    auto_delete_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class LegalHold(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_holds"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(250))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[LegalHoldStatus] = mapped_column(
        Enum(LegalHoldStatus, native_enum=False), default=LegalHoldStatus.ACTIVE, index=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True
    )
    released_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeletionRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deletion_requests"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("security_users.id", ondelete="RESTRICT"), index=True
    )
    resource_type: Mapped[RetentionResourceType] = mapped_column(
        Enum(RetentionResourceType, native_enum=False), index=True
    )
    resource_id: Mapped[str] = mapped_column(String(100), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[DeletionStatus] = mapped_column(
        Enum(DeletionStatus, native_enum=False), default=DeletionStatus.REQUESTED, index=True
    )
    hold_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("legal_holds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    decision_reason: Mapped[str | None] = mapped_column(Text)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
