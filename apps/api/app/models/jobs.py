from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class JobStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class JobPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class JobKind(StrEnum):
    DOCUMENT_REPROCESS = "document.reprocess"
    SEARCH_DOCUMENT_REINDEX = "search.document_reindex"
    SEARCH_ORG_REBUILD = "search.organization_rebuild"
    SEARCH_DUPLICATE_SCAN = "search.duplicate_scan"
    MATTER_INTELLIGENCE_REBUILD = "matter.intelligence_rebuild"
    EVIDENCE_MATTER_REBUILD = "evidence.matter_rebuild"
    ANALYTICS_SNAPSHOT = "analytics.snapshot"
    ANALYTICS_RISK_REBUILD = "analytics.risk_rebuild"
    OPERATIONS_DUE_SWEEP = "operations.due_sweep"
    CORPUS_RESOLVE_CITATIONS = "corpus.resolve_citations"
    LEGAL_DATA_FEED_SYNC = "legal_data.feed_sync"
    LEGAL_DATA_INTEGRITY_SWEEP = "legal_data.integrity_sweep"
    EVIDENCE_BUNDLE_BUILD = "evidence.bundle_build"
    EVIDENCE_BUNDLE_FINALIZE = "evidence.bundle_finalize"
    SYSTEM_HEALTH_CHECK = "system.health_check"
    BACKUP_RUN = "system.backup_run"
    RESTORE_VERIFY = "system.restore_verify"


class JobEventLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class JobAttemptStatus(StrEnum):
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"
    CANCELLED = "cancelled"


class WorkerStatus(StrEnum):
    ONLINE = "online"
    DRAINING = "draining"
    OFFLINE = "offline"


class BackgroundQueue(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "background_queues"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_background_queue_org_name"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=4)
    max_per_minute: Mapped[int] = mapped_column(Integer, default=120)
    default_max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    lease_seconds: Mapped[int] = mapped_column(Integer, default=300)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BackgroundJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_background_job_org_idempotency"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    requested_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    queue_name: Mapped[str] = mapped_column(String(80), default="default", index=True)
    kind: Mapped[JobKind] = mapped_column(String(80), index=True)
    status: Mapped[JobStatus] = mapped_column(String(30), default=JobStatus.QUEUED, index=True)
    priority: Mapped[JobPriority] = mapped_column(String(20), default=JobPriority.NORMAL, index=True)
    priority_value: Mapped[int] = mapped_column(Integer, default=50, index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(240), nullable=True)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    backoff_base_seconds: Mapped[int] = mapped_column(Integer, default=10)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    leased_by_worker_id: Mapped[UUID | None] = mapped_column(ForeignKey("background_workers.id", ondelete="SET NULL"), nullable=True, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=100)
    progress_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    handler_version: Mapped[str] = mapped_column(String(40), default="v1")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BackgroundJobAttempt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "background_job_attempts"
    __table_args__ = (UniqueConstraint("job_id", "attempt_number", name="uq_background_job_attempt_number"),)

    job_id: Mapped[UUID] = mapped_column(ForeignKey("background_jobs.id", ondelete="CASCADE"), index=True)
    worker_id: Mapped[UUID | None] = mapped_column(ForeignKey("background_workers.id", ondelete="SET NULL"), nullable=True, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[JobAttemptStatus] = mapped_column(String(30), default=JobAttemptStatus.LEASED, index=True)
    leased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BackgroundJobEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "background_job_events"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("background_jobs.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    level: Mapped[JobEventLevel] = mapped_column(String(20), default=JobEventLevel.INFO, index=True)
    message: Mapped[str] = mapped_column(String(1000))
    progress_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BackgroundWorker(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "background_workers"
    __table_args__ = (UniqueConstraint("organization_id", "worker_key", name="uq_background_worker_org_key"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    worker_key: Mapped[str] = mapped_column(String(220), index=True)
    hostname: Mapped[str] = mapped_column(String(255))
    pid: Mapped[int] = mapped_column(Integer)
    status: Mapped[WorkerStatus] = mapped_column(String(30), default=WorkerStatus.ONLINE, index=True)
    queues_json: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    current_job_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    jobs_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BackgroundJobDependency(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "background_job_dependencies"
    __table_args__ = (UniqueConstraint("job_id", "depends_on_job_id", name="uq_background_job_dependency"),)

    job_id: Mapped[UUID] = mapped_column(ForeignKey("background_jobs.id", ondelete="CASCADE"), index=True)
    depends_on_job_id: Mapped[UUID] = mapped_column(ForeignKey("background_jobs.id", ondelete="CASCADE"), index=True)
    required_status: Mapped[JobStatus] = mapped_column(String(30), default=JobStatus.SUCCEEDED)


class BackgroundJobArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "background_job_artifacts"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("background_jobs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
