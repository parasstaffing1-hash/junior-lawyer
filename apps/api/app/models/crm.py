from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.security import AccessEffect, ConfidentialityLevel, MatterAccessLevel, MatterAccessMode


class LeadStatus(StrEnum):
    NEW = "new"
    QUALIFYING = "qualifying"
    CONFLICT_CHECK = "conflict_check"
    ONBOARDING = "onboarding"
    CONVERTED = "converted"
    LOST = "lost"


class ClientStatus(StrEnum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"


class ClientType(StrEnum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"


class ConflictCheckStatus(StrEnum):
    PENDING = "pending"
    REVIEW_REQUIRED = "review_required"
    CLEARED = "cleared"
    CONFLICT_FOUND = "conflict_found"
    OVERRIDDEN = "overridden"


class ConflictCandidateType(StrEnum):
    CLIENT = "client"
    CONTACT = "contact"
    MATTER = "matter"


class KYCStatus(StrEnum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OnboardingStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    COMPLETE = "complete"
    BLOCKED = "blocked"


class EngagementStatus(StrEnum):
    DRAFT = "draft"
    PENDING_SIGNATURE = "pending_signature"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    CLOSED = "closed"


class CRMTaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class CRMTaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class CommunicationType(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    MEETING = "meeting"
    WHATSAPP = "whatsapp"
    LETTER = "letter"
    OTHER = "other"


class TimeEntryStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    INVOICED = "invoiced"


class PortalAccessStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    REVOKED = "revoked"


class CRMLead(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "crm_leads"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(250), index=True)
    company_name: Mapped[str | None] = mapped_column(String(250), index=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(64), index=True)
    source: Mapped[str | None] = mapped_column(String(120), index=True)
    practice_area: Mapped[str | None] = mapped_column(String(160), index=True)
    language: Mapped[str] = mapped_column(String(20), default="bilingual")
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus, native_enum=False), default=LeadStatus.NEW, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(String(300))
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Client(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "clients"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_number: Mapped[str] = mapped_column(String(80), index=True)
    client_type: Mapped[ClientType] = mapped_column(Enum(ClientType, native_enum=False), default=ClientType.INDIVIDUAL, index=True)
    status: Mapped[ClientStatus] = mapped_column(Enum(ClientStatus, native_enum=False), default=ClientStatus.PROSPECT, index=True)
    display_name: Mapped[str] = mapped_column(String(300), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(300), index=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(64), index=True)
    preferred_language: Mapped[str] = mapped_column(String(20), default="bilingual")
    billing_address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(120), default="India")
    tax_id_last4: Mapped[str | None] = mapped_column(String(4))
    source_lead_id: Mapped[UUID | None] = mapped_column(ForeignKey("crm_leads.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (UniqueConstraint("organization_id", "client_number", name="uq_client_org_number"),)


class ClientSecurityProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_security_profiles"
    __table_args__ = (UniqueConstraint("client_id", name="uq_client_security_profile_client"),)

    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    classification: Mapped[ConfidentialityLevel] = mapped_column(
        Enum(ConfidentialityLevel, native_enum=False), default=ConfidentialityLevel.CONFIDENTIAL, index=True
    )
    access_mode: Mapped[MatterAccessMode] = mapped_column(
        Enum(MatterAccessMode, native_enum=False), default=MatterAccessMode.ORGANIZATION, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)


class ClientAccessGrant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_access_grants"
    __table_args__ = (UniqueConstraint("client_id", "membership_id", name="uq_client_grant_membership"),)

    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    effect: Mapped[AccessEffect] = mapped_column(Enum(AccessEffect, native_enum=False), default=AccessEffect.ALLOW, index=True)
    access_level: Mapped[MatterAccessLevel] = mapped_column(Enum(MatterAccessLevel, native_enum=False), default=MatterAccessLevel.VIEW, index=True)
    granted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(500))


class ClientContact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_contacts"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(250), index=True)
    role_title: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(64), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class ConflictCheck(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conflict_checks"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[UUID | None] = mapped_column(ForeignKey("crm_leads.id", ondelete="SET NULL"), nullable=True, index=True)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    subject_name: Mapped[str] = mapped_column(String(300), index=True)
    related_parties_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[ConflictCheckStatus] = mapped_column(Enum(ConflictCheckStatus, native_enum=False), default=ConflictCheckStatus.PENDING, index=True)
    search_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConflictCandidate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conflict_candidates"

    conflict_check_id: Mapped[UUID] = mapped_column(ForeignKey("conflict_checks.id", ondelete="CASCADE"), index=True)
    candidate_type: Mapped[ConflictCandidateType] = mapped_column(Enum(ConflictCandidateType, native_enum=False), index=True)
    candidate_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    candidate_name: Mapped[str] = mapped_column(String(300), index=True)
    reason: Mapped[str] = mapped_column(String(300))
    match_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ClientOnboarding(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_onboarding"
    __table_args__ = (UniqueConstraint("client_id", name="uq_onboarding_client"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    status: Mapped[OnboardingStatus] = mapped_column(Enum(OnboardingStatus, native_enum=False), default=OnboardingStatus.NOT_STARTED, index=True)
    conflict_check_id: Mapped[UUID | None] = mapped_column(ForeignKey("conflict_checks.id", ondelete="SET NULL"), nullable=True)
    identity_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    address_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    engagement_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_cleared: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClientKYCRecord(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_kyc_records"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[KYCStatus] = mapped_column(Enum(KYCStatus, native_enum=False), default=KYCStatus.PENDING, index=True)
    document_reference: Mapped[str | None] = mapped_column(String(200))
    identifier_last4: Mapped[str | None] = mapped_column(String(4))
    verified_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Engagement(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "engagements"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    scope: Mapped[str | None] = mapped_column(Text)
    fee_structure: Mapped[str | None] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    agreed_fee: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[EngagementStatus] = mapped_column(Enum(EngagementStatus, native_enum=False), default=EngagementStatus.DRAFT, index=True)
    engagement_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class MatterClientLink(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_client_links"
    __table_args__ = (UniqueConstraint("matter_id", "client_id", name="uq_matter_client_link"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    relationship_role: Mapped[str] = mapped_column(String(100), default="client")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class ClientNote(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_notes"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    author_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(250))
    body: Mapped[str] = mapped_column(Text)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)


class CRMTask(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "crm_tasks"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    lead_id: Mapped[UUID | None] = mapped_column(ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True, index=True)
    assigned_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[CRMTaskStatus] = mapped_column(Enum(CRMTaskStatus, native_enum=False), default=CRMTaskStatus.TODO, index=True)
    priority: Mapped[CRMTaskPriority] = mapped_column(Enum(CRMTaskPriority, native_enum=False), default=CRMTaskPriority.MEDIUM, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClientCommunication(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_communications"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    communication_type: Mapped[CommunicationType] = mapped_column(Enum(CommunicationType, native_enum=False), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    direction: Mapped[str] = mapped_column(String(20), default="outbound")
    subject: Mapped[str | None] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    external_reference: Mapped[str | None] = mapped_column(String(300))


class TimeEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "time_entries"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("security_users.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    minutes: Mapped[int] = mapped_column(Integer)
    narrative: Mapped[str] = mapped_column(Text)
    billable: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    hourly_rate: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[TimeEntryStatus] = mapped_column(Enum(TimeEntryStatus, native_enum=False), default=TimeEntryStatus.DRAFT, index=True)


class ClientPortalAccess(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_portal_access"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("client_contacts.id", ondelete="SET NULL"), nullable=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    status: Mapped[PortalAccessStatus] = mapped_column(Enum(PortalAccessStatus, native_enum=False), default=PortalAccessStatus.INVITED, index=True)
    invited_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    permissions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
