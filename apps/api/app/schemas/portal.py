from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.portal import PortalRequestStatus, PortalShareType
from app.models.collaboration import ClientDocumentApprovalStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PortalActivationRequest(BaseModel):
    invite_token: str = Field(min_length=20)
    password: str = Field(min_length=12, max_length=512)


class PortalLoginRequest(BaseModel):
    organization_slug: str = Field(min_length=1, max_length=120)
    email: str
    password: str


class PortalSessionRead(BaseModel):
    email: str
    client_id: UUID
    client_name: str
    csrf_token: str
    expires_at: datetime


class PortalShareCreate(BaseModel):
    portal_access_id: UUID
    matter_id: UUID | None = None
    share_type: PortalShareType
    resource_id: UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    message: str | None = None
    can_download: bool = False
    metadata: dict = Field(default_factory=dict)


class PortalShareRead(ORMModel):
    id: UUID
    client_id: UUID
    matter_id: UUID | None
    share_type: PortalShareType
    resource_id: UUID | None
    title: str
    message: str | None
    can_download: bool
    shared_at: datetime
    metadata_json: dict


class PortalMessageCreate(BaseModel):
    portal_access_id: UUID | None = None
    matter_id: UUID | None = None
    body: str = Field(min_length=1, max_length=20000)


class PortalMessageRead(ORMModel):
    id: UUID
    matter_id: UUID | None
    sender_type: str
    body: str
    sent_at: datetime
    read_at: datetime | None


class PortalRequestCreate(BaseModel):
    portal_access_id: UUID
    matter_id: UUID | None = None
    request_type: str = "information"
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    due_at: datetime | None = None


class PortalRequestRead(ORMModel):
    id: UUID
    matter_id: UUID | None
    request_type: str
    title: str
    description: str | None
    status: PortalRequestStatus
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class PortalRequestUpdate(BaseModel):
    status: PortalRequestStatus


class PortalDashboard(BaseModel):
    client_id: UUID
    client_name: str
    shares: list[PortalShareRead]
    messages: list[PortalMessageRead]
    requests: list[PortalRequestRead]
    outstanding_invoice_count: int
    outstanding_amount: str


class PortalClientApprovalRead(ORMModel):
    id: UUID
    matter_id: UUID
    document_id: UUID
    document_version_id: UUID
    title: str
    message: str | None
    status: ClientDocumentApprovalStatus
    responded_at: datetime | None
    response_note: str | None
    created_at: datetime


class PortalClientApprovalDecision(BaseModel):
    status: ClientDocumentApprovalStatus
    note: str | None = None
