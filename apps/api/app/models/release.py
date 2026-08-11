from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class ReleaseRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    HELD = "held"
    APPROVED = "approved"
    REJECTED = "rejected"
    ERROR = "error"


class ReleaseStageKind(StrEnum):
    BACKEND_TESTS = "backend_tests"
    LEGAL_QA = "legal_qa"
    MIGRATIONS = "migrations"
    FRONTEND_STATIC = "frontend_static"
    LOAD = "load"
    SECURITY = "security"
    ARTIFACT = "artifact"
    ROLLBACK = "rollback"


class ReleaseStageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PerformanceScenarioKind(StrEnum):
    API_SMOKE = "api_smoke"
    SEARCH_CONCURRENCY = "search_concurrency"
    UPLOAD_CONCURRENCY = "upload_concurrency"
    WORKER_QUEUE = "worker_queue"
    OCR_QUEUE = "ocr_queue"
    GENERIC_HTTP = "generic_http"


class PerformanceRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class SecurityCheckKind(StrEnum):
    AUTHORIZATION = "authorization"
    ETHICAL_WALL = "ethical_wall"
    IDOR = "idor"
    CSRF = "csrf"
    SESSION = "session"
    UPLOAD = "upload"
    RATE_LIMIT = "rate_limit"
    PROMPT_INJECTION = "prompt_injection"
    HEADERS = "headers"


class SecurityRunStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class ReleaseArtifactKind(StrEnum):
    SOURCE_ZIP = "source_zip"
    CHECKSUM = "checksum"
    QA_REPORT = "qa_report"
    LOAD_REPORT = "load_report"
    SECURITY_REPORT = "security_report"
    RELEASE_MANIFEST = "release_manifest"
    OTHER = "other"


class RollbackPointStatus(StrEnum):
    READY = "ready"
    USED = "used"
    INVALID = "invalid"


class DeploymentDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ReleasePipeline(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "release_pipelines"
    __table_args__ = (UniqueConstraint("organization_id", "pipeline_key", name="uq_release_pipeline_org_key"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    pipeline_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(260))
    version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    require_qa_gate: Mapped[bool] = mapped_column(Boolean, default=True)
    require_security_zero_critical: Mapped[bool] = mapped_column(Boolean, default=True)
    require_migration_roundtrip: Mapped[bool] = mapped_column(Boolean, default=True)
    require_frontend_static: Mapped[bool] = mapped_column(Boolean, default=True)
    require_load_gate: Mapped[bool] = mapped_column(Boolean, default=True)
    thresholds_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ReleaseRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "release_runs"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    pipeline_id: Mapped[UUID] = mapped_column(ForeignKey("release_pipelines.id", ondelete="RESTRICT"), index=True)
    requested_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[ReleaseRunStatus] = mapped_column(String(30), default=ReleaseRunStatus.QUEUED, index=True)
    app_version: Mapped[str] = mapped_column(String(80), index=True)
    build_ref: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    commit_ref: Mapped[str | None] = mapped_column(String(180), nullable=True)
    environment: Mapped[str] = mapped_column(String(60), default="candidate", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qa_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    security_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    load_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    migration_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    frontend_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class ReleaseStageRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "release_stage_runs"
    __table_args__ = (UniqueConstraint("release_run_id", "stage_key", name="uq_release_stage_run_key"),)

    release_run_id: Mapped[UUID] = mapped_column(ForeignKey("release_runs.id", ondelete="CASCADE"), index=True)
    stage_key: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[ReleaseStageKind] = mapped_column(String(40), index=True)
    status: Mapped[ReleaseStageStatus] = mapped_column(String(30), default=ReleaseStageStatus.PENDING, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class PerformanceScenario(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "performance_scenarios"
    __table_args__ = (UniqueConstraint("organization_id", "scenario_key", name="uq_performance_scenario_org_key"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    scenario_key: Mapped[str] = mapped_column(String(140), index=True)
    name: Mapped[str] = mapped_column(String(260))
    kind: Mapped[PerformanceScenarioKind] = mapped_column(String(40), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    critical: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    method: Mapped[str] = mapped_column(String(12), default="GET")
    path: Mapped[str] = mapped_column(String(500), default="/health")
    concurrency: Mapped[int] = mapped_column(Integer, default=8)
    request_count: Mapped[int] = mapped_column(Integer, default=100)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=15.0)
    max_p95_ms: Mapped[float] = mapped_column(Float, default=1000.0)
    min_success_rate: Mapped[float] = mapped_column(Float, default=0.99)
    max_error_rate: Mapped[float] = mapped_column(Float, default=0.01)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    headers_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class PerformanceRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "performance_runs"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    release_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("release_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    scenario_id: Mapped[UUID] = mapped_column(ForeignKey("performance_scenarios.id", ondelete="CASCADE"), index=True)
    status: Mapped[PerformanceRunStatus] = mapped_column(String(30), default=PerformanceRunStatus.QUEUED, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)
    requests_per_second: Mapped[float] = mapped_column(Float, default=0.0)
    p50_ms: Mapped[float] = mapped_column(Float, default=0.0)
    p95_ms: Mapped[float] = mapped_column(Float, default=0.0)
    p99_ms: Mapped[float] = mapped_column(Float, default=0.0)
    max_ms: Mapped[float] = mapped_column(Float, default=0.0)
    error_rate: Mapped[float] = mapped_column(Float, default=0.0)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class SecurityTestCase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "security_test_cases"
    __table_args__ = (UniqueConstraint("organization_id", "case_key", name="uq_security_test_case_org_key"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    case_key: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[SecurityCheckKind] = mapped_column(String(40), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    critical: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SecurityTestRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "security_test_runs"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    release_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("release_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("security_test_cases.id", ondelete="CASCADE"), index=True)
    status: Mapped[SecurityRunStatus] = mapped_column(String(30), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_json: Mapped[dict] = mapped_column(JSON, default=dict)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class ReleaseArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "release_artifacts"

    release_run_id: Mapped[UUID] = mapped_column(ForeignKey("release_runs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[ReleaseArtifactKind] = mapped_column(String(40), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RollbackPoint(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rollback_points"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    release_run_id: Mapped[UUID] = mapped_column(ForeignKey("release_runs.id", ondelete="CASCADE"), index=True)
    app_version: Mapped[str] = mapped_column(String(80), index=True)
    database_revision: Mapped[str | None] = mapped_column(String(160), nullable=True)
    release_artifact_id: Mapped[UUID | None] = mapped_column(ForeignKey("release_artifacts.id", ondelete="SET NULL"), nullable=True)
    backup_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("backup_runs.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[RollbackPointStatus] = mapped_column(String(30), default=RollbackPointStatus.READY, index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DeploymentApproval(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_approvals"
    __table_args__ = (UniqueConstraint("release_run_id", "membership_id", name="uq_deployment_approval_run_member"),)

    release_run_id: Mapped[UUID] = mapped_column(ForeignKey("release_runs.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    decision: Mapped[DeploymentDecision] = mapped_column(String(30), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
