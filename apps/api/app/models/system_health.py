from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class HealthTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WORKER = "worker"


class IncidentSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class BackupStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    VERIFIED = "verified"


class BackupTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WORKER = "worker"


class BackupArtifactKind(StrEnum):
    DATABASE = "database"
    DOCUMENTS = "documents"
    MANIFEST = "manifest"


class RestoreDrillStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    REVIEWED = "reviewed"


class SystemHealthRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_health_runs"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    requested_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    trigger: Mapped[HealthTrigger] = mapped_column(String(30), default=HealthTrigger.MANUAL, index=True)
    status: Mapped[HealthStatus] = mapped_column(String(30), default=HealthStatus.UNKNOWN, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class SystemHealthComponent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_health_components"
    __table_args__ = (UniqueConstraint("run_id", "component_key", name="uq_system_health_component_run_key"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("system_health_runs.id", ondelete="CASCADE"), index=True)
    component_key: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[HealthStatus] = mapped_column(String(30), default=HealthStatus.UNKNOWN, index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_en: Mapped[str] = mapped_column(String(900))
    message_hi: Mapped[str | None] = mapped_column(String(900), nullable=True)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SystemIncident(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_incidents"
    __table_args__ = (UniqueConstraint("organization_id", "fingerprint", name="uq_system_incident_org_fingerprint"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    component_key: Mapped[str] = mapped_column(String(120), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[IncidentSeverity] = mapped_column(String(30), default=IncidentSeverity.WARNING, index=True)
    status: Mapped[IncidentStatus] = mapped_column(String(30), default=IncidentStatus.OPEN, index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemIncidentEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_incident_events"

    incident_id: Mapped[UUID] = mapped_column(ForeignKey("system_incidents.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(String(1200))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BackupPolicy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "backup_policies"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(220))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    include_database: Mapped[bool] = mapped_column(Boolean, default=True)
    include_documents: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_rrule: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    max_backups: Mapped[int] = mapped_column(Integer, default=30)
    destination_kind: Mapped[str] = mapped_column(String(40), default="local")
    destination_path: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    encryption_mode: Mapped[str] = mapped_column(String(60), default="none")
    rpo_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    rto_minutes: Mapped[int] = mapped_column(Integer, default=240)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BackupRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "backup_runs"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    policy_id: Mapped[UUID | None] = mapped_column(ForeignKey("backup_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    trigger: Mapped[BackupTrigger] = mapped_column(String(30), default=BackupTrigger.MANUAL, index=True)
    status: Mapped[BackupStatus] = mapped_column(String(30), default=BackupStatus.QUEUED, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    database_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    documents_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BackupArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "backup_artifacts"

    backup_run_id: Mapped[UUID] = mapped_column(ForeignKey("backup_runs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[BackupArtifactKind] = mapped_column(String(30), index=True)
    storage_path: Mapped[str] = mapped_column(String(1400))
    filename: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RestoreDrill(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "restore_drills"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    backup_run_id: Mapped[UUID] = mapped_column(ForeignKey("backup_runs.id", ondelete="CASCADE"), index=True)
    requested_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[RestoreDrillStatus] = mapped_column(String(30), default=RestoreDrillStatus.QUEUED, index=True)
    scope: Mapped[str] = mapped_column(String(60), default="verification_only")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    database_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    documents_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    artifact_hashes_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    document_count_verified: Mapped[int] = mapped_column(Integer, default=0)
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RecoveryObjective(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "recovery_objectives"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_recovery_objective_org"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    updated_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    target_rpo_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    target_rto_minutes: Mapped[int] = mapped_column(Integer, default=240)
    restore_verification_days: Mapped[int] = mapped_column(Integer, default=30)
    max_queue_lag_seconds: Mapped[int] = mapped_column(Integer, default=900)
    worker_stale_seconds: Mapped[int] = mapped_column(Integer, default=90)
    slow_job_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    min_storage_free_percent: Mapped[int] = mapped_column(Integer, default=15)
    max_database_latency_ms: Mapped[int] = mapped_column(Integer, default=500)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemMetricSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_metric_snapshots"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    overall_status: Mapped[HealthStatus] = mapped_column(String(30), default=HealthStatus.UNKNOWN, index=True)
    database_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_free_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_total_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_oldest_age_seconds: Mapped[int] = mapped_column(Integer, default=0)
    dead_letter_count: Mapped[int] = mapped_column(Integer, default=0)
    slow_job_count: Mapped[int] = mapped_column(Integer, default=0)
    online_worker_count: Mapped[int] = mapped_column(Integer, default=0)
    stale_worker_count: Mapped[int] = mapped_column(Integer, default=0)
    search_index_age_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tesseract_available: Mapped[bool] = mapped_column(Boolean, default=False)
    local_ai_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    remote_ai_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
