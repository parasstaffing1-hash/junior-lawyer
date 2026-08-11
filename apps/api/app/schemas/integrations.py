from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.integrations import IntegrationProvider, IntegrationStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SecretReferenceInput(BaseModel):
    secret_key: str = Field(min_length=2, max_length=120)
    reference: str = Field(min_length=3, max_length=1000)
    required: bool = True


class IntegrationConnectionCreate(BaseModel):
    connection_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(min_length=2, max_length=220)
    provider: IntegrationProvider
    capabilities: list[str] = Field(default_factory=list, max_length=30)
    config: dict = Field(default_factory=dict)
    secrets: list[SecretReferenceInput] = Field(default_factory=list, max_length=30)


class IntegrationConnectionRead(ORMModel):
    id: UUID
    organization_id: UUID
    connection_key: str
    display_name: str
    provider: IntegrationProvider
    status: IntegrationStatus
    enabled: bool
    capabilities_json: list
    config_json: dict
    last_connected_at: datetime | None
    last_error: str | None
    created_by_membership_id: UUID
    created_at: datetime
    updated_at: datetime


class IntegrationSecretRead(ORMModel):
    id: UUID
    connection_id: UUID
    secret_key: str
    reference: str
    required: bool
    last_verified_at: datetime | None


class IntegrationHealthRead(ORMModel):
    id: UUID
    connection_id: UUID
    status: IntegrationStatus
    checked_at: datetime
    live_probe: bool
    latency_ms: int | None
    checks_json: list
    error_message: str | None


class IntegrationCatalogItem(BaseModel):
    provider: IntegrationProvider
    title: str
    description: str
    capabilities: list[str]
    required_config: list[str]
    optional_config: list[str]
    required_secrets: list[str]
    official_docs: list[str]


class IntegrationDashboard(BaseModel):
    connections: list[IntegrationConnectionRead]
    health: list[IntegrationHealthRead]
    provider_counts: dict[str, int]
    connected_count: int
    degraded_count: int


class ConnectionTestRequest(BaseModel):
    live_probe: bool = False


class ConnectionTestResult(BaseModel):
    connection_id: UUID
    status: IntegrationStatus
    live_probe: bool
    checks: list[dict]
    latency_ms: int | None = None
    error: str | None = None


class GmailSendRequest(BaseModel):
    to: list[str] = Field(min_length=1, max_length=50)
    cc: list[str] = Field(default_factory=list, max_length=50)
    bcc: list[str] = Field(default_factory=list, max_length=50)
    subject: str = Field(min_length=1, max_length=998)
    text_body: str = Field(default="", max_length=500_000)
    html_body: str | None = Field(default=None, max_length=500_000)
    reply_to: str | None = Field(default=None, max_length=320)
    internal_resource_type: str | None = Field(default=None, max_length=100)
    internal_resource_id: str | None = Field(default=None, max_length=120)


class CalendarEventRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=1024)
    start: datetime
    end: datetime
    timezone: str = Field(default="Asia/Kolkata", max_length=100)
    description: str | None = Field(default=None, max_length=50_000)
    location: str | None = Field(default=None, max_length=1000)
    attendees: list[str] = Field(default_factory=list, max_length=100)
    send_updates: str = Field(default="none", pattern=r"^(all|externalOnly|none)$")
    internal_resource_type: str | None = Field(default=None, max_length=100)
    internal_resource_id: str | None = Field(default=None, max_length=120)


class PaymentLinkRequest(BaseModel):
    amount_paise: int = Field(gt=0, le=1_000_000_000_00)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    description: str = Field(min_length=1, max_length=255)
    reference_id: str | None = Field(default=None, max_length=40)
    customer_name: str | None = Field(default=None, max_length=120)
    customer_email: str | None = Field(default=None, max_length=320)
    customer_phone: str | None = Field(default=None, max_length=30)
    expire_by: int | None = Field(default=None, gt=0)
    notify_email: bool = False
    notify_sms: bool = False
    allow_partial: bool = False
    internal_resource_type: str | None = Field(default="invoice", max_length=100)
    internal_resource_id: str | None = Field(default=None, max_length=120)


class DocusignEnvelopeRequest(BaseModel):
    document_version_id: UUID
    document_name: str | None = Field(default=None, max_length=255)
    signer_name: str = Field(min_length=1, max_length=200)
    signer_email: str = Field(min_length=3, max_length=320)
    email_subject: str = Field(min_length=1, max_length=500)
    status: str = Field(default="sent", pattern=r"^(sent|created)$")
    internal_resource_type: str | None = Field(default="document_version", max_length=100)
    internal_resource_id: str | None = Field(default=None, max_length=120)


class OutboundWebhookRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    event_type: str = Field(min_length=1, max_length=200)
    payload: dict
    idempotency_key: str | None = Field(default=None, max_length=240)


class DeliveryResult(BaseModel):
    provider: IntegrationProvider
    operation: str
    external_resource_id: str | None = None
    external_url: str | None = None
    metadata: dict = Field(default_factory=dict)


class WebhookEndpointCreate(BaseModel):
    connection_id: UUID
    endpoint_key: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")
    signing_secret_reference: str | None = Field(default=None, max_length=1000)
    event_types: list[str] = Field(default_factory=list, max_length=100)


class WebhookEndpointRead(ORMModel):
    id: UUID
    organization_id: UUID
    connection_id: UUID
    endpoint_key: str
    signing_secret_reference: str | None
    enabled: bool
    event_types_json: list
    metadata_json: dict


class OAuthStartRequest(BaseModel):
    redirect_uri: str = Field(min_length=8, max_length=1000)
    scopes: list[str] = Field(default_factory=list, max_length=30)


class OAuthStartResult(BaseModel):
    authorization_url: str
    expires_at: datetime
    note: str


class WebhookEventRead(ORMModel):
    id: UUID
    endpoint_id: UUID
    external_event_id: str
    event_type: str
    status: str
    body_sha256: str
    signature_valid: bool
    normalized_payload_json: dict
    received_at: datetime
    processed_at: datetime | None
    error_message: str | None

class OfficialLegalImportRequest(BaseModel):
    kind: str = Field(pattern=r"^(statute|judgment)$")
    source_url: str = Field(min_length=8, max_length=2000)
    payload: dict
    source_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    feed_id: UUID | None = None
