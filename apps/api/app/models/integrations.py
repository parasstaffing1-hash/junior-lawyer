from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class IntegrationProvider(StrEnum):
    GOOGLE_WORKSPACE = "google_workspace"
    RAZORPAY = "razorpay"
    DOCUSIGN = "docusign"
    GENERIC_WEBHOOK = "generic_webhook"
    OFFICIAL_LEGAL_IMPORT = "official_legal_import"


class IntegrationStatus(StrEnum):
    DRAFT = "draft"
    CONFIGURED = "configured"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISABLED = "disabled"


class IntegrationSyncStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IntegrationDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class WebhookEventStatus(StrEnum):
    RECEIVED = "received"
    VERIFIED = "verified"
    PROCESSED = "processed"
    REJECTED = "rejected"
    FAILED = "failed"


class DeliveryStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class IntegrationConnection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_connections"
    __table_args__ = (UniqueConstraint("organization_id", "connection_key", name="uq_integration_connection_org_key"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    connection_key: Mapped[str] = mapped_column(String(120), index=True)
    display_name: Mapped[str] = mapped_column(String(220))
    provider: Mapped[IntegrationProvider] = mapped_column(String(50), index=True)
    status: Mapped[IntegrationStatus] = mapped_column(String(30), default=IntegrationStatus.DRAFT, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    capabilities_json: Mapped[list] = mapped_column(JSON, default=list)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    created_by_membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="RESTRICT"), index=True)


class IntegrationSecretReference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_secret_references"
    __table_args__ = (UniqueConstraint("connection_id", "secret_key", name="uq_integration_secret_connection_key"),)

    connection_id: Mapped[UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True)
    secret_key: Mapped[str] = mapped_column(String(120), index=True)
    reference: Mapped[str] = mapped_column(String(1000))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationOAuthState(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_oauth_states"

    connection_id: Mapped[UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    redirect_uri: Mapped[str] = mapped_column(String(1000))
    requested_scopes_json: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_accounts"
    __table_args__ = (UniqueConstraint("connection_id", "external_subject", name="uq_integration_account_subject"),)

    connection_id: Mapped[UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True)
    external_subject: Mapped[str] = mapped_column(String(500), index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(250), nullable=True)
    scopes_json: Mapped[list] = mapped_column(JSON, default=list)
    sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class IntegrationSyncRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_sync_runs"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True)
    direction: Mapped[IntegrationDirection] = mapped_column(String(30), index=True)
    resource_type: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[IntegrationSyncStatus] = mapped_column(String(30), default=IntegrationSyncStatus.QUEUED, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scanned_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    cursor_before: Mapped[str | None] = mapped_column(Text, nullable=True)
    cursor_after: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1600), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class IntegrationResourceMapping(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_resource_mappings"
    __table_args__ = (UniqueConstraint("connection_id", "internal_resource_type", "internal_resource_id", "external_resource_type", name="uq_integration_mapping_internal_external_type"),)

    connection_id: Mapped[UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True)
    internal_resource_type: Mapped[str] = mapped_column(String(100), index=True)
    internal_resource_id: Mapped[str] = mapped_column(String(120), index=True)
    external_resource_type: Mapped[str] = mapped_column(String(100), index=True)
    external_resource_id: Mapped[str] = mapped_column(String(700), index=True)
    external_url: Mapped[str | None] = mapped_column(String(1400), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class IntegrationWebhookEndpoint(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_webhook_endpoints"
    __table_args__ = (UniqueConstraint("endpoint_key", name="uq_integration_webhook_endpoint_key"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True)
    endpoint_key: Mapped[str] = mapped_column(String(160), index=True)
    signing_secret_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    event_types_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class IntegrationWebhookEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_webhook_events"
    __table_args__ = (UniqueConstraint("endpoint_id", "external_event_id", name="uq_integration_webhook_event_external"),)

    endpoint_id: Mapped[UUID] = mapped_column(ForeignKey("integration_webhook_endpoints.id", ondelete="CASCADE"), index=True)
    external_event_id: Mapped[str] = mapped_column(String(500), index=True)
    event_type: Mapped[str] = mapped_column(String(240), index=True)
    status: Mapped[WebhookEventStatus] = mapped_column(String(30), default=WebhookEventStatus.RECEIVED, index=True)
    body_sha256: Mapped[str] = mapped_column(String(64), index=True)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    normalized_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1200), nullable=True)


class IntegrationDeliveryAttempt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_delivery_attempts"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True)
    operation: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[DeliveryStatus] = mapped_column(String(30), default=DeliveryStatus.QUEUED, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    request_sha256: Mapped[str] = mapped_column(String(64), index=True)
    external_resource_id: Mapped[str | None] = mapped_column(String(700), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(1400), nullable=True)
    response_metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(String(1600), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationHealthCheck(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_health_checks"

    connection_id: Mapped[UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True)
    status: Mapped[IntegrationStatus] = mapped_column(String(30), index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    live_probe: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checks_json: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(String(1200), nullable=True)
