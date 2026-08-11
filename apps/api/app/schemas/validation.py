from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.validation import (
    PilotCheckStatus,
    ReleaseCandidateStatus,
    ValidationCampaignStatus,
    ValidationDatasetKind,
    ValidationEvidenceKind,
    ValidationExecutionMode,
    ValidationRunStatus,
    ValidationScenarioKind,
    ValidationSeverity,
    ValidationSignoffDecision,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ValidationScenarioRead(ORMModel):
    id: UUID
    scenario_key: str
    name: str
    description: str
    kind: ValidationScenarioKind
    execution_mode: ValidationExecutionMode
    severity: ValidationSeverity
    enabled: bool
    thresholds_json: dict
    instructions_json: dict


class ValidationCampaignCreate(BaseModel):
    name: str = Field(min_length=3, max_length=260)
    candidate_version: str = Field(default="0.29.0-rc.1", min_length=3, max_length=100)
    release_run_id: UUID | None = None
    environment_id: UUID | None = None
    build_ref: str | None = Field(default=None, max_length=180)


class ValidationCampaignRead(ORMModel):
    id: UUID
    organization_id: UUID
    release_run_id: UUID | None
    environment_id: UUID | None
    name: str
    candidate_version: str
    build_ref: str | None
    status: ValidationCampaignStatus
    started_at: datetime | None
    finished_at: datetime | None
    summary_json: dict
    snapshot_hash: str | None
    created_at: datetime


class ValidationScenarioResultCreate(BaseModel):
    scenario_id: UUID
    status: ValidationRunStatus
    duration_ms: int = Field(default=0, ge=0)
    metrics_json: dict = Field(default_factory=dict)
    details_json: dict = Field(default_factory=dict)
    error: str | None = None


class ValidationScenarioRunRead(ORMModel):
    id: UUID
    campaign_id: UUID
    scenario_id: UUID
    status: ValidationRunStatus
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int
    metrics_json: dict
    details_json: dict
    error: str | None
    snapshot_hash: str | None


class ValidationEvidenceCreate(BaseModel):
    kind: ValidationEvidenceKind
    label: str = Field(min_length=2, max_length=300)
    storage_path: str | None = None
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    size_bytes: int = Field(default=0, ge=0)
    metadata_json: dict = Field(default_factory=dict)


class ValidationEvidenceRead(ORMModel):
    id: UUID
    scenario_run_id: UUID
    kind: ValidationEvidenceKind
    label: str
    storage_path: str | None
    sha256: str | None
    size_bytes: int
    metadata_json: dict


class PilotReadinessUpdate(BaseModel):
    status: PilotCheckStatus
    note: str | None = None
    evidence_json: dict = Field(default_factory=dict)


class PilotReadinessRead(ORMModel):
    id: UUID
    campaign_id: UUID
    check_key: str
    category: str
    label: str
    required: bool
    status: PilotCheckStatus
    evidence_json: dict
    note: str | None
    reviewed_by_membership_id: UUID | None
    reviewed_at: datetime | None


class ValidationDatasetCreate(BaseModel):
    kind: ValidationDatasetKind
    name: str = Field(min_length=2, max_length=260)
    record_count: int = Field(default=0, ge=0)
    page_count: int = Field(default=0, ge=0)
    size_bytes: int = Field(default=0, ge=0)
    generation_seed: int | None = None
    manifest_path: str | None = None
    sha256: str = Field(min_length=64, max_length=64)
    metadata_json: dict = Field(default_factory=dict)


class ValidationDatasetRead(ORMModel):
    id: UUID
    organization_id: UUID
    campaign_id: UUID | None
    kind: ValidationDatasetKind
    name: str
    record_count: int
    page_count: int
    size_bytes: int
    generation_seed: int | None
    manifest_path: str | None
    sha256: str
    metadata_json: dict


class ValidationSignoffCreate(BaseModel):
    decision: ValidationSignoffDecision
    role_label: str = Field(min_length=2, max_length=120)
    note: str | None = None


class ValidationSignoffRead(ORMModel):
    id: UUID
    campaign_id: UUID
    membership_id: UUID
    decision: ValidationSignoffDecision
    role_label: str
    note: str | None
    decided_at: datetime


class ReleaseCandidateManifestRead(ORMModel):
    id: UUID
    campaign_id: UUID
    release_run_id: UUID | None
    environment_id: UUID | None
    candidate_version: str
    database_revision: str | None
    artifact_sha256: str | None
    status: ReleaseCandidateStatus
    gate_json: dict
    manifest_json: dict
    snapshot_hash: str
    created_at: datetime


class ValidationCampaignDetail(BaseModel):
    campaign: ValidationCampaignRead
    scenarios: list[ValidationScenarioRead]
    runs: list[ValidationScenarioRunRead]
    checks: list[PilotReadinessRead]
    datasets: list[ValidationDatasetRead]
    signoffs: list[ValidationSignoffRead]
    manifest: ReleaseCandidateManifestRead | None
    gate: dict


class ValidationDashboard(BaseModel):
    scenarios: list[ValidationScenarioRead]
    campaigns: list[ValidationCampaignRead]
    summary: dict
