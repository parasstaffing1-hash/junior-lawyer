from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.deployment import (
    DeploymentEnvironmentKind,
    DeploymentRolloutStatus,
    DeploymentStepKind,
    DeploymentStepStatus,
    DeploymentStrategy,
    SecretReferenceProvider,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DeploymentEnvironmentCreate(BaseModel):
    environment_key: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=220)
    kind: DeploymentEnvironmentKind = DeploymentEnvironmentKind.PRODUCTION
    base_url: str = Field(min_length=8, max_length=600)
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    tls_required: bool = True
    object_storage_required: bool = True
    change_window_required: bool = True


class DeploymentEnvironmentRead(ORMModel):
    id: UUID
    organization_id: UUID
    environment_key: str
    name: str
    kind: DeploymentEnvironmentKind
    base_url: str
    strategy: DeploymentStrategy
    enabled: bool
    tls_required: bool
    object_storage_required: bool
    change_window_required: bool
    current_release_run_id: UUID | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class DeploymentServiceRead(ORMModel):
    id: UUID
    environment_id: UUID
    service_key: str
    image_ref: str | None
    replicas: int
    enabled: bool
    health_path: str | None
    queue_names: str | None
    metadata_json: dict


class DeploymentChangeWindowCreate(BaseModel):
    environment_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(min_length=3, max_length=900)
    emergency: bool = False


class DeploymentChangeWindowRead(ORMModel):
    id: UUID
    environment_id: UUID
    approved_by_membership_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str
    emergency: bool


class DeploymentSecretReferenceCreate(BaseModel):
    environment_id: UUID
    secret_key: str = Field(min_length=2, max_length=180)
    provider: SecretReferenceProvider = SecretReferenceProvider.ENVIRONMENT
    reference: str = Field(min_length=1, max_length=1000)
    required: bool = True


class DeploymentSecretReferenceRead(ORMModel):
    id: UUID
    environment_id: UUID
    secret_key: str
    provider: SecretReferenceProvider
    reference: str
    required: bool
    last_verified_at: datetime | None


class DeploymentRolloutCreate(BaseModel):
    environment_id: UUID
    release_run_id: UUID
    rollback_point_id: UUID
    change_window_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=4000)


class DeploymentStepUpdate(BaseModel):
    status: DeploymentStepStatus
    message: str | None = Field(default=None, max_length=1200)
    evidence_json: dict = Field(default_factory=dict)


class DeploymentRolloutStepRead(ORMModel):
    id: UUID
    rollout_id: UUID
    step_key: str
    kind: DeploymentStepKind
    sequence: int
    status: DeploymentStepStatus
    started_at: datetime | None
    finished_at: datetime | None
    message: str | None
    evidence_json: dict


class DeploymentRolloutRead(ORMModel):
    id: UUID
    organization_id: UUID
    environment_id: UUID
    release_run_id: UUID
    rollback_point_id: UUID
    change_window_id: UUID | None
    requested_by_membership_id: UUID
    status: DeploymentRolloutStatus
    started_at: datetime | None
    finished_at: datetime | None
    snapshot_hash: str | None
    notes: str | None
    metadata_json: dict
    created_at: datetime


class DeploymentRolloutDetail(BaseModel):
    rollout: DeploymentRolloutRead
    steps: list[DeploymentRolloutStepRead]


class ReadinessCheck(BaseModel):
    """One runtime readiness probe result."""

    key: str
    passed: bool
    critical: bool
    message: str


class RuntimeReadiness(BaseModel):
    ready: bool
    checks: list[ReadinessCheck]
    app_version: str
    build_ref: str | None
    commit_ref: str | None


class DeploymentDashboard(BaseModel):
    environments: list[DeploymentEnvironmentRead]
    services: list[DeploymentServiceRead]
    rollouts: list[DeploymentRolloutRead]
    change_windows: list[DeploymentChangeWindowRead]
    secrets: list[DeploymentSecretReferenceRead]
    runtime_readiness: RuntimeReadiness
