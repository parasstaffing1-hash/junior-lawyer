from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ReleasePipelineRead(ORMModel):
    id: UUID
    pipeline_key: str
    name: str
    version: int
    enabled: bool
    require_qa_gate: bool
    require_security_zero_critical: bool
    require_migration_roundtrip: bool
    require_frontend_static: bool
    require_load_gate: bool
    thresholds_json: dict


class ReleaseRunCreate(BaseModel):
    build_ref: str | None = Field(default=None, max_length=180)
    commit_ref: str | None = Field(default=None, max_length=180)
    environment: str = Field(default="candidate", max_length=60)


class ReleaseRunRead(ORMModel):
    id: UUID
    pipeline_id: UUID
    status: str
    app_version: str
    build_ref: str | None
    commit_ref: str | None
    environment: str
    qa_passed: bool | None
    security_passed: bool | None
    load_passed: bool | None
    migration_passed: bool | None
    frontend_passed: bool | None
    started_at: datetime | None
    finished_at: datetime | None
    summary_json: dict
    snapshot_hash: str | None
    created_at: datetime


class ReleaseStageRead(ORMModel):
    id: UUID
    stage_key: str
    kind: str
    status: str
    duration_ms: int
    details_json: dict
    error: str | None


class PerformanceScenarioRead(ORMModel):
    id: UUID
    scenario_key: str
    name: str
    kind: str
    enabled: bool
    critical: bool
    method: str
    path: str
    concurrency: int
    request_count: int
    timeout_seconds: float
    max_p95_ms: float
    min_success_rate: float
    max_error_rate: float


class PerformanceRunRead(ORMModel):
    id: UUID
    scenario_id: UUID
    status: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    error_rate: float
    result_json: dict
    snapshot_hash: str | None
    created_at: datetime


class SecurityCaseRead(ORMModel):
    id: UUID
    case_key: str
    title: str
    kind: str
    enabled: bool
    critical: bool
    description: str | None
    request_json: dict
    expected_json: dict


class SecurityRunRead(ORMModel):
    id: UUID
    case_id: UUID
    status: str
    actual_json: dict
    details_json: dict
    error: str | None
    snapshot_hash: str | None
    created_at: datetime


class ReleaseArtifactRead(ORMModel):
    id: UUID
    kind: str
    filename: str
    sha256: str
    size_bytes: int
    metadata_json: dict


class RollbackPointRead(ORMModel):
    id: UUID
    app_version: str
    database_revision: str | None
    status: str
    verified_at: datetime | None
    notes: str | None


class DeploymentApprovalCreate(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=2000)


class DeploymentApprovalRead(ORMModel):
    id: UUID
    membership_id: UUID
    decision: str
    note: str | None
    decided_at: datetime


class ReleaseGateSummary(BaseModel):
    """Gate verdict returned by POST /release/runs/{run_id}/evaluate.

    The same shape is persisted as ReleaseRun.summary_json.
    """

    passed: bool
    reasons: list[str]
    critical_security_failures: int
    stage_status: dict[str, str]
    performance_runs: int
    security_runs: int
    rollback_ready: bool
    artifact_passed: bool


class ReleaseRunDetail(BaseModel):
    run: ReleaseRunRead
    stages: list[ReleaseStageRead]
    performance: list[PerformanceRunRead]
    security: list[SecurityRunRead]
    artifacts: list[ReleaseArtifactRead]
    rollback_points: list[RollbackPointRead]
    approvals: list[DeploymentApprovalRead]
    gate: dict


class ReleaseDashboard(BaseModel):
    pipeline: ReleasePipelineRead
    latest_runs: list[ReleaseRunRead]
    performance_scenarios: list[PerformanceScenarioRead]
    security_cases: list[SecurityCaseRead]
    summary: dict

class StageResultCreate(BaseModel):
    status: str = Field(pattern="^(passed|failed|skipped)$")
    duration_ms: int = Field(default=0, ge=0)
    details_json: dict = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=10000)


class PerformanceResultCreate(BaseModel):
    scenario_id: UUID
    latencies_ms: list[float] = Field(default_factory=list, max_length=200000)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    details_json: dict = Field(default_factory=dict)


class SecurityResultCreate(BaseModel):
    case_id: UUID
    actual_json: dict = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=10000)


class RollbackPointCreate(BaseModel):
    database_revision: str | None = Field(default=None, max_length=160)
    release_artifact_id: UUID | None = None
    backup_run_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    verified: bool = True

class ReleaseArtifactCreate(BaseModel):
    kind: str = Field(default="other", max_length=40)
    filename: str = Field(min_length=1, max_length=500)
    sha256: str = Field(pattern="^[0-9a-fA-F]{64}$")
    size_bytes: int = Field(default=0, ge=0)
    storage_path: str | None = Field(default=None, max_length=4000)
    metadata_json: dict = Field(default_factory=dict)
