from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.security import (
    AccessEffect,
    AuditOutcome,
    ConfidentialityLevel,
    DeletionStatus,
    DocumentAccessLevel,
    LegalHoldStatus,
    MatterAccessLevel,
    MatterAccessMode,
    MembershipStatus,
    OrganizationRole,
    OrganizationStatus,
    PolicyDecision,
    RetentionResourceType,
    UserStatus,
)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    status: OrganizationStatus
    default_language: str
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class SecurityUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str
    status: UserStatus
    locale: str
    mfa_enrolled: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: OrganizationRole
    status: MembershipStatus
    is_default: bool
    created_at: datetime
    updated_at: datetime
    user: SecurityUserRead | None = None


class ActorRead(BaseModel):
    user_id: UUID
    membership_id: UUID
    organization_id: UUID
    email: str
    display_name: str
    role: OrganizationRole
    mfa_enrolled: bool


class BootstrapRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=250)
    organization_slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    admin_email: str = Field(min_length=3, max_length=320)
    admin_name: str = Field(min_length=2, max_length=250)
    password: str = Field(min_length=12, max_length=1024)
    bootstrap_secret: str | None = Field(default=None, max_length=500)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    organization_slug: str | None = Field(default=None, max_length=120)


class LoginResponse(BaseModel):
    actor: ActorRead
    organization: OrganizationRead
    csrf_token: str
    expires_at: datetime
    absolute_expires_at: datetime


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=2, max_length=250)
    password: str = Field(min_length=12, max_length=1024)
    locale: str = Field(default="en", pattern="^(en|hi|bilingual)$")
    role: OrganizationRole = OrganizationRole.LAWYER


class MembershipUpdateRequest(BaseModel):
    role: OrganizationRole | None = None
    status: MembershipStatus | None = None


class SecurityPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    session_idle_timeout_minutes: int
    session_absolute_lifetime_hours: int
    max_concurrent_sessions: int
    password_min_length: int
    max_failed_login_attempts: int
    lockout_minutes: int
    allow_remote_ai_default: bool
    allow_exports_default: bool
    require_mfa_for_remote_ai: bool
    require_mfa_for_highly_confidential: bool
    audit_log_retention_days: int
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class SecurityPolicyUpdate(BaseModel):
    session_idle_timeout_minutes: int | None = Field(default=None, ge=5, le=10080)
    session_absolute_lifetime_hours: int | None = Field(default=None, ge=1, le=720)
    max_concurrent_sessions: int | None = Field(default=None, ge=1, le=100)
    password_min_length: int | None = Field(default=None, ge=8, le=128)
    max_failed_login_attempts: int | None = Field(default=None, ge=2, le=50)
    lockout_minutes: int | None = Field(default=None, ge=1, le=1440)
    allow_remote_ai_default: bool | None = None
    allow_exports_default: bool | None = None
    require_mfa_for_remote_ai: bool | None = None
    require_mfa_for_highly_confidential: bool | None = None
    audit_log_retention_days: int | None = Field(default=None, ge=30, le=36500)


class MatterSecurityProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    matter_id: UUID
    classification: ConfidentialityLevel
    access_mode: MatterAccessMode
    remote_ai_policy: PolicyDecision
    export_policy: PolicyDecision
    notes: str | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class MatterSecurityProfileUpdate(BaseModel):
    classification: ConfidentialityLevel | None = None
    access_mode: MatterAccessMode | None = None
    remote_ai_policy: PolicyDecision | None = None
    export_policy: PolicyDecision | None = None
    notes: str | None = Field(default=None, max_length=4000)


class MatterGrantCreate(BaseModel):
    membership_id: UUID
    effect: AccessEffect = AccessEffect.ALLOW
    access_level: MatterAccessLevel = MatterAccessLevel.VIEW
    allow_remote_ai: bool | None = None
    allow_export: bool | None = None
    expires_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class MatterGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    matter_id: UUID
    membership_id: UUID
    effect: AccessEffect
    access_level: MatterAccessLevel
    allow_remote_ai: bool | None
    allow_export: bool | None
    expires_at: datetime | None
    reason: str | None
    granted_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentGrantCreate(BaseModel):
    membership_id: UUID
    effect: AccessEffect = AccessEffect.ALLOW
    access_level: DocumentAccessLevel = DocumentAccessLevel.VIEW
    expires_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class DocumentGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    membership_id: UUID
    effect: AccessEffect
    access_level: DocumentAccessLevel
    expires_at: datetime | None
    reason: str | None
    granted_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AccessDecisionRead(BaseModel):
    allowed: bool
    reason: str
    matter_access_level: MatterAccessLevel | None = None
    remote_ai_allowed: bool | None = None
    export_allowed: bool | None = None
    classification: ConfidentialityLevel | None = None


class AuditEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    sequence: int
    occurred_at: datetime
    actor_user_id: UUID | None
    actor_membership_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: AuditOutcome
    reason: str | None
    request_id: str | None
    metadata_json: dict
    previous_hash: str
    event_hash: str
    signature_mode: str


class AuditVerifyRead(BaseModel):
    valid: bool
    checked_entries: int
    first_invalid_sequence: int | None = None
    reason: str | None = None
    signed: bool


class RetentionPolicyCreate(BaseModel):
    resource_type: RetentionResourceType
    retention_days: int = Field(ge=1, le=36500)
    enabled: bool = True
    auto_delete_enabled: bool = False
    notes: str | None = Field(default=None, max_length=4000)


class RetentionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    resource_type: RetentionResourceType
    retention_days: int
    enabled: bool
    auto_delete_enabled: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class LegalHoldCreate(BaseModel):
    matter_id: UUID
    label: str = Field(min_length=2, max_length=250)
    reason: str = Field(min_length=2, max_length=8000)


class LegalHoldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    matter_id: UUID
    label: str
    reason: str
    status: LegalHoldStatus
    created_by_user_id: UUID | None
    released_by_user_id: UUID | None
    released_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DeletionRequestCreate(BaseModel):
    resource_type: RetentionResourceType
    resource_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=2, max_length=8000)


class DeletionDecisionRequest(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=4000)


class DeletionRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    requested_by_user_id: UUID
    resource_type: RetentionResourceType
    resource_id: str
    reason: str
    status: DeletionStatus
    hold_id: UUID | None
    decision_reason: str | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    executed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SecurityOverviewRead(BaseModel):
    actor: ActorRead
    organization: OrganizationRead
    policy: SecurityPolicyRead
    members: int
    active_sessions: int
    restricted_matters: int
    ethical_wall_matters: int
    active_legal_holds: int
    pending_deletions: int
    audit_entries: int
