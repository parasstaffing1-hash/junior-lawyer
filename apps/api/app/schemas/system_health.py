from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.system_health import HealthStatus
from pydantic import BaseModel, ConfigDict, Field


class HealthComponentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    component_key: str
    category: str
    status: HealthStatus
    latency_ms: int | None
    message_en: str
    message_hi: str | None
    metrics_json: dict
    checked_at: datetime


class HealthRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    trigger: str
    status: HealthStatus
    started_at: datetime
    finished_at: datetime | None
    summary_json: dict
    snapshot_hash: str | None
    created_at: datetime


class HealthRunDetail(BaseModel):
    run: HealthRunRead
    components: list[HealthComponentRead]


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    component_key: str
    fingerprint: str
    severity: str
    status: str
    title: str
    description: str
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class IncidentUpdate(BaseModel):
    action: str = Field(pattern="^(acknowledge|resolve|reopen)$")
    note: str | None = Field(default=None, max_length=1500)


class RecoveryObjectiveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    target_rpo_minutes: int
    target_rto_minutes: int
    restore_verification_days: int
    max_queue_lag_seconds: int
    worker_stale_seconds: int
    slow_job_seconds: int
    min_storage_free_percent: int
    max_database_latency_ms: int
    metadata_json: dict
    updated_at: datetime


class RecoveryObjectiveUpdate(BaseModel):
    target_rpo_minutes: int | None = Field(default=None, ge=1, le=10080)
    target_rto_minutes: int | None = Field(default=None, ge=1, le=10080)
    restore_verification_days: int | None = Field(default=None, ge=1, le=365)
    max_queue_lag_seconds: int | None = Field(default=None, ge=30, le=604800)
    worker_stale_seconds: int | None = Field(default=None, ge=30, le=3600)
    slow_job_seconds: int | None = Field(default=None, ge=60, le=604800)
    min_storage_free_percent: int | None = Field(default=None, ge=1, le=90)
    max_database_latency_ms: int | None = Field(default=None, ge=10, le=30000)


class BackupPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=220)
    enabled: bool = True
    include_database: bool = True
    include_documents: bool = True
    schedule_rrule: str | None = Field(default=None, max_length=500)
    retention_days: int = Field(default=30, ge=1, le=3650)
    max_backups: int = Field(default=30, ge=1, le=1000)
    destination_kind: str = Field(default="local", pattern="^(local|external)$")
    destination_path: str | None = Field(default=None, max_length=1200)
    encryption_mode: str = Field(default="none", pattern="^(none|external)$")
    rpo_minutes: int = Field(default=1440, ge=1, le=10080)
    rto_minutes: int = Field(default=240, ge=1, le=10080)


class BackupPolicyUpdate(BaseModel):
    enabled: bool | None = None
    include_database: bool | None = None
    include_documents: bool | None = None
    schedule_rrule: str | None = Field(default=None, max_length=500)
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    max_backups: int | None = Field(default=None, ge=1, le=1000)
    destination_kind: str | None = Field(default=None, pattern="^(local|external)$")
    destination_path: str | None = Field(default=None, max_length=1200)
    encryption_mode: str | None = Field(default=None, pattern="^(none|external)$")
    rpo_minutes: int | None = Field(default=None, ge=1, le=10080)
    rto_minutes: int | None = Field(default=None, ge=1, le=10080)


class BackupPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    enabled: bool
    include_database: bool
    include_documents: bool
    schedule_rrule: str | None
    retention_days: int
    max_backups: int
    destination_kind: str
    destination_path: str | None
    encryption_mode: str
    rpo_minutes: int
    rto_minutes: int
    last_run_at: datetime | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class BackupArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    filename: str
    size_bytes: int
    sha256: str
    encrypted: bool
    metadata_json: dict
    created_at: datetime


class BackupRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    policy_id: UUID | None
    trigger: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    total_bytes: int
    manifest_sha256: str | None
    database_status: str | None
    documents_status: str | None
    error: str | None
    metadata_json: dict
    created_at: datetime


class BackupRunDetail(BaseModel):
    run: BackupRunRead
    artifacts: list[BackupArtifactRead]


class RestoreDrillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    backup_run_id: UUID
    status: str
    scope: str
    started_at: datetime | None
    finished_at: datetime | None
    reviewed_at: datetime | None
    database_verified: bool
    documents_verified: bool
    artifact_hashes_verified: bool
    document_count_verified: int
    result_hash: str | None
    notes: str | None
    metadata_json: dict
    created_at: datetime


class RestoreDrillReview(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class MetricSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    captured_at: datetime
    overall_status: str
    database_latency_ms: int | None
    storage_free_bytes: int | None
    storage_total_bytes: int | None
    queue_oldest_age_seconds: int
    dead_letter_count: int
    slow_job_count: int
    online_worker_count: int
    stale_worker_count: int
    search_index_age_seconds: int | None
    tesseract_available: bool
    local_ai_configured: bool
    remote_ai_configured: bool
    snapshot_hash: str
    metrics_json: dict


class SystemHealthDashboard(BaseModel):
    latest_run: HealthRunRead | None
    components: list[HealthComponentRead]
    open_incidents: list[IncidentRead]
    recovery_objectives: RecoveryObjectiveRead
    backup_policies: list[BackupPolicyRead]
    recent_backups: list[BackupRunRead]
    recent_restore_drills: list[RestoreDrillRead]
    latest_metrics: MetricSnapshotRead | None
