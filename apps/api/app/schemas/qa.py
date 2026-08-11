from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    suite_id: UUID
    case_key: str
    title: str
    category: str
    evaluator: str
    status: str
    weight: float
    critical: bool
    input_json: dict
    expected_json: dict
    source_note: str | None
    source_hash: str | None
    tags_json: list
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class EvaluationSuiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    suite_key: str
    name: str
    description: str | None
    version: int
    enabled: bool
    default_gate: bool
    tags_json: list
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class EvaluationSuiteDetail(BaseModel):
    suite: EvaluationSuiteRead
    cases: list[EvaluationCaseRead]


class EvaluationCaseCreate(BaseModel):
    case_key: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=500)
    category: str
    evaluator: str = Field(min_length=1, max_length=100)
    weight: float = Field(default=1.0, ge=0.0, le=100.0)
    critical: bool = False
    input_json: dict = Field(default_factory=dict)
    expected_json: dict = Field(default_factory=dict)
    source_note: str | None = None
    tags_json: list = Field(default_factory=list)
    metadata_json: dict = Field(default_factory=dict)


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    suite_id: UUID
    status: str
    trigger: str
    app_version: str | None
    build_ref: str | None
    started_at: datetime | None
    finished_at: datetime | None
    total_cases: int
    passed_cases: int
    failed_cases: int
    skipped_cases: int
    critical_failures: int
    overall_score: float
    duration_ms: int
    snapshot_hash: str | None
    summary_json: dict
    created_at: datetime


class EvaluationCaseRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    case_id: UUID
    status: str
    score: float
    duration_ms: int
    actual_json: dict
    expected_json: dict
    details_json: dict
    error: str | None


class QAFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    case_run_id: UUID | None
    category: str
    severity: str
    code: str
    message: str
    details_json: dict
    resolved: bool
    created_at: datetime


class EvaluationRunDetail(BaseModel):
    run: EvaluationRunRead
    case_runs: list[EvaluationCaseRunRead]
    findings: list[QAFindingRead]
    metrics: list[dict]
    gate: dict | None = None


class ReleaseGateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    enabled: bool
    min_overall_score: float
    max_critical_failures: int
    require_security_zero_failures: bool
    require_citation_zero_failures: bool
    category_thresholds_json: dict
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class ReleaseGateUpdate(BaseModel):
    min_overall_score: float | None = Field(default=None, ge=0.0, le=1.0)
    max_critical_failures: int | None = Field(default=None, ge=0, le=1000)
    require_security_zero_failures: bool | None = None
    require_citation_zero_failures: bool | None = None
    category_thresholds_json: dict | None = None


class EvaluationRunCreate(BaseModel):
    build_ref: str | None = Field(default=None, max_length=160)


class QADashboard(BaseModel):
    suites: list[EvaluationSuiteRead]
    latest_runs: list[EvaluationRunRead]
    default_gate: ReleaseGateRead | None
    latest_gate_result: dict | None
    summary: dict
