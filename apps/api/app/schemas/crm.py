from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.crm import (
    ClientStatus, ClientType, CommunicationType, ConflictCheckStatus, CRMTaskPriority,
    CRMTaskStatus, EngagementStatus, KYCStatus, LeadStatus, PortalAccessStatus, TimeEntryStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=250)
    company_name: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str | None = None
    practice_area: str | None = None
    language: str = "bilingual"
    summary: str | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    owner_membership_id: UUID | None = None


class LeadUpdate(BaseModel):
    status: LeadStatus | None = None
    owner_membership_id: UUID | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    summary: str | None = None


class LeadRead(ORMModel):
    id: UUID
    organization_id: UUID
    name: str
    company_name: str | None
    email: str | None
    phone: str | None
    source: str | None
    practice_area: str | None
    language: str
    status: LeadStatus
    summary: str | None
    next_action: str | None
    next_action_at: datetime | None
    owner_membership_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ClientCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=300)
    legal_name: str | None = None
    client_type: ClientType = ClientType.INDIVIDUAL
    email: str | None = None
    phone: str | None = None
    preferred_language: str = "bilingual"
    billing_address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "India"
    tax_id_last4: str | None = Field(default=None, max_length=4)
    source_lead_id: UUID | None = None


class ClientUpdate(BaseModel):
    status: ClientStatus | None = None
    display_name: str | None = None
    legal_name: str | None = None
    email: str | None = None
    phone: str | None = None
    preferred_language: str | None = None
    billing_address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class ClientRead(ORMModel):
    id: UUID
    organization_id: UUID
    client_number: str
    client_type: ClientType
    status: ClientStatus
    display_name: str
    legal_name: str | None
    email: str | None
    phone: str | None
    preferred_language: str
    billing_address: str | None
    city: str | None
    state: str | None
    country: str
    source_lead_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ConflictCheckCreate(BaseModel):
    subject_name: str = Field(min_length=2, max_length=300)
    related_parties: list[str] = Field(default_factory=list, max_length=50)
    lead_id: UUID | None = None
    client_id: UUID | None = None


class ConflictCandidateRead(ORMModel):
    id: UUID
    candidate_type: str
    candidate_id: UUID | None
    candidate_name: str
    reason: str
    match_score: float
    metadata_json: dict


class ConflictCheckRead(ORMModel):
    id: UUID
    organization_id: UUID
    lead_id: UUID | None
    client_id: UUID | None
    subject_name: str
    related_parties_json: list
    status: ConflictCheckStatus
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
    candidates: list[ConflictCandidateRead] = Field(default_factory=list)


class ConflictDecision(BaseModel):
    status: ConflictCheckStatus
    review_note: str = Field(min_length=3, max_length=3000)

    @field_validator("status")
    @classmethod
    def allowed_status(cls, value: ConflictCheckStatus):
        if value not in {ConflictCheckStatus.CLEARED, ConflictCheckStatus.CONFLICT_FOUND, ConflictCheckStatus.OVERRIDDEN}:
            raise ValueError("Review decision must be cleared, conflict_found, or overridden")
        return value


class ConvertLeadRequest(BaseModel):
    client_type: ClientType = ClientType.INDIVIDUAL
    legal_name: str | None = None


class OnboardingRead(ORMModel):
    id: UUID
    client_id: UUID
    status: str
    conflict_check_id: UUID | None
    identity_complete: bool
    address_complete: bool
    engagement_complete: bool
    conflict_cleared: bool
    notes: str | None
    completed_at: datetime | None


class KYCRecordCreate(BaseModel):
    document_type: str = Field(min_length=2, max_length=100)
    document_reference: str | None = None
    identifier_last4: str | None = Field(default=None, max_length=4)
    expires_on: date | None = None
    notes: str | None = None


class KYCVerifyRequest(BaseModel):
    status: KYCStatus
    notes: str | None = None


class KYCRecordRead(ORMModel):
    id: UUID
    client_id: UUID
    document_type: str
    status: KYCStatus
    document_reference: str | None
    identifier_last4: str | None
    verified_at: datetime | None
    expires_on: date | None
    notes: str | None
    created_at: datetime


class EngagementCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    matter_id: UUID | None = None
    scope: str | None = None
    fee_structure: str | None = None
    currency: str = "INR"
    agreed_fee: float | None = Field(default=None, ge=0)
    status: EngagementStatus = EngagementStatus.DRAFT


class EngagementRead(ORMModel):
    id: UUID
    client_id: UUID
    matter_id: UUID | None
    title: str
    scope: str | None
    fee_structure: str | None
    currency: str
    agreed_fee: float | None
    status: EngagementStatus
    signed_at: datetime | None
    created_at: datetime


class MatterOpenRequest(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str | None = None
    practice_area: str | None = None
    primary_language: str = "bilingual"
    engagement_id: UUID | None = None
    team_membership_ids: list[UUID] = Field(default_factory=list, max_length=50)


class ContactCreate(BaseModel):
    name: str
    role_title: str | None = None
    email: str | None = None
    phone: str | None = None
    is_primary: bool = False
    notes: str | None = None


class ContactRead(ORMModel):
    id: UUID
    client_id: UUID
    name: str
    role_title: str | None
    email: str | None
    phone: str | None
    is_primary: bool
    notes: str | None


class NoteCreate(BaseModel):
    title: str | None = None
    body: str = Field(min_length=1, max_length=20000)
    matter_id: UUID | None = None
    is_private: bool = False


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    client_id: UUID | None = None
    matter_id: UUID | None = None
    lead_id: UUID | None = None
    assigned_membership_id: UUID | None = None
    due_at: datetime | None = None
    priority: CRMTaskPriority = CRMTaskPriority.MEDIUM


class TaskUpdate(BaseModel):
    status: CRMTaskStatus | None = None
    priority: CRMTaskPriority | None = None
    assigned_membership_id: UUID | None = None
    due_at: datetime | None = None


class TaskRead(ORMModel):
    id: UUID
    title: str
    description: str | None
    client_id: UUID | None
    matter_id: UUID | None
    lead_id: UUID | None
    assigned_membership_id: UUID | None
    due_at: datetime | None
    status: CRMTaskStatus
    priority: CRMTaskPriority
    completed_at: datetime | None
    created_at: datetime


class CommunicationCreate(BaseModel):
    communication_type: CommunicationType
    occurred_at: datetime
    direction: str = "outbound"
    subject: str | None = None
    summary: str = Field(min_length=1, max_length=20000)
    matter_id: UUID | None = None
    external_reference: str | None = None


class TimeEntryCreate(BaseModel):
    client_id: UUID | None = None
    matter_id: UUID | None = None
    work_date: date
    minutes: int = Field(gt=0, le=1440)
    narrative: str = Field(min_length=2, max_length=5000)
    billable: bool = True
    hourly_rate: float | None = Field(default=None, ge=0)
    currency: str = "INR"


class TimeEntryRead(ORMModel):
    id: UUID
    client_id: UUID | None
    matter_id: UUID | None
    user_id: UUID
    work_date: date
    minutes: int
    narrative: str
    billable: bool
    hourly_rate: float | None
    currency: str
    status: TimeEntryStatus
    created_at: datetime


class PortalInviteCreate(BaseModel):
    contact_id: UUID | None = None
    email: str
    permissions: dict = Field(default_factory=lambda: {"documents": "view", "messages": True})


class PortalAccessRead(ORMModel):
    id: UUID
    client_id: UUID
    contact_id: UUID | None
    email: str
    status: PortalAccessStatus
    invited_at: datetime | None
    activated_at: datetime | None
    revoked_at: datetime | None
    permissions_json: dict


class CRMOverview(BaseModel):
    leads_open: int
    clients_active: int
    conflict_reviews: int
    onboarding_open: int
    tasks_due: int
    unbilled_minutes: int

class ClientMatterSummary(BaseModel):
    id: str
    title: str
    status: str
    reference_number: str | None


class ClientNoteRead(BaseModel):
    id: str
    title: str | None
    body: str
    matter_id: str | None
    is_private: bool
    created_at: datetime


class ClientCommunicationRead(BaseModel):
    id: str
    type: str
    occurred_at: datetime
    direction: str
    subject: str | None
    summary: str
    matter_id: str | None


class ClientDetail(BaseModel):
    """The composite payload GET /crm/clients/{id} has always returned.

    It was assembled inline in the route, so it never reached the OpenAPI
    schema and the web client had to fall back to plain ClientRead.
    """

    client: ClientRead
    onboarding: OnboardingRead
    contacts: list[ContactRead]
    kyc: list[KYCRecordRead]
    engagements: list[EngagementRead]
    matters: list[ClientMatterSummary]
    notes: list[ClientNoteRead]
    communications: list[ClientCommunicationRead]
    portal_access: list[PortalAccessRead]


class OnboardingUpdate(BaseModel):
    address_complete: bool | None = None
    engagement_complete: bool | None = None
    notes: str | None = None
    mark_complete: bool = False

from app.models.security import AccessEffect, ConfidentialityLevel, MatterAccessLevel, MatterAccessMode

class ClientSecurityUpdate(BaseModel):
    classification: ConfidentialityLevel
    access_mode: MatterAccessMode
    notes: str | None = None


class ClientSecurityRead(ORMModel):
    id: UUID
    client_id: UUID
    classification: ConfidentialityLevel
    access_mode: MatterAccessMode
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ClientGrantCreate(BaseModel):
    membership_id: UUID
    effect: AccessEffect = AccessEffect.ALLOW
    access_level: MatterAccessLevel = MatterAccessLevel.WORK
    reason: str | None = None


class ClientGrantRead(ORMModel):
    id: UUID
    client_id: UUID
    membership_id: UUID
    effect: AccessEffect
    access_level: MatterAccessLevel
    reason: str | None
    expires_at: datetime | None
