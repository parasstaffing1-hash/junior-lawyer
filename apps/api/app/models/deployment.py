from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class DeploymentEnvironmentKind(StrEnum):
    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentStrategy(StrEnum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    RECREATE = "recreate"


class DeploymentRolloutStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class DeploymentStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DeploymentStepKind(StrEnum):
    PREFLIGHT = "preflight"
    BACKUP = "backup"
    MIGRATION = "migration"
    API = "api"
    WORKERS = "workers"
    WEB = "web"
    HEALTH = "health"
    TRAFFIC = "traffic"
    POSTCHECK = "postcheck"


class SecretReferenceProvider(StrEnum):
    ENVIRONMENT = "environment"
    DOCKER_SECRET = "docker_secret"
    VAULT = "vault"
    CLOUD_SECRET_MANAGER = "cloud_secret_manager"
    KUBERNETES_SECRET = "kubernetes_secret"
    OTHER = "other"


class DeploymentEnvironment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_environments"
    __table_args__ = (
        UniqueConstraint("organization_id", "environment_key", name="uq_deployment_environment_org_key"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    environment_key: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(220))
    kind: Mapped[DeploymentEnvironmentKind] = mapped_column(String(30), default=DeploymentEnvironmentKind.STAGING, index=True)
    base_url: Mapped[str] = mapped_column(String(600))
    strategy: Mapped[DeploymentStrategy] = mapped_column(String(30), default=DeploymentStrategy.ROLLING)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    tls_required: Mapped[bool] = mapped_column(Boolean, default=True)
    object_storage_required: Mapped[bool] = mapped_column(Boolean, default=True)
    change_window_required: Mapped[bool] = mapped_column(Boolean, default=True)
    current_release_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("release_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DeploymentServiceProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_service_profiles"
    __table_args__ = (
        UniqueConstraint("environment_id", "service_key", name="uq_deployment_service_environment_key"),
    )

    environment_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_environments.id", ondelete="CASCADE"), index=True)
    service_key: Mapped[str] = mapped_column(String(80), index=True)
    image_ref: Mapped[str | None] = mapped_column(String(700), nullable=True)
    replicas: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    queue_names: Mapped[str | None] = mapped_column(String(600), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DeploymentChangeWindow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_change_windows"

    environment_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_environments.id", ondelete="CASCADE"), index=True)
    approved_by_membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="RESTRICT"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reason: Mapped[str] = mapped_column(String(900))
    emergency: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DeploymentRollout(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_rollouts"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    environment_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_environments.id", ondelete="RESTRICT"), index=True)
    release_run_id: Mapped[UUID] = mapped_column(ForeignKey("release_runs.id", ondelete="RESTRICT"), index=True)
    rollback_point_id: Mapped[UUID] = mapped_column(ForeignKey("rollback_points.id", ondelete="RESTRICT"), index=True)
    change_window_id: Mapped[UUID | None] = mapped_column(ForeignKey("deployment_change_windows.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by_membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="RESTRICT"), index=True)
    status: Mapped[DeploymentRolloutStatus] = mapped_column(String(30), default=DeploymentRolloutStatus.PLANNED, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DeploymentRolloutStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_rollout_steps"
    __table_args__ = (
        UniqueConstraint("rollout_id", "step_key", name="uq_deployment_rollout_step_key"),
    )

    rollout_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_rollouts.id", ondelete="CASCADE"), index=True)
    step_key: Mapped[str] = mapped_column(String(100), index=True)
    kind: Mapped[DeploymentStepKind] = mapped_column(String(30), index=True)
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[DeploymentStepStatus] = mapped_column(String(30), default=DeploymentStepStatus.PENDING, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DeploymentSecretReference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_secret_references"
    __table_args__ = (
        UniqueConstraint("environment_id", "secret_key", name="uq_deployment_secret_environment_key"),
    )

    environment_id: Mapped[UUID] = mapped_column(ForeignKey("deployment_environments.id", ondelete="CASCADE"), index=True)
    secret_key: Mapped[str] = mapped_column(String(180), index=True)
    provider: Mapped[SecretReferenceProvider] = mapped_column(String(40), default=SecretReferenceProvider.ENVIRONMENT)
    reference: Mapped[str] = mapped_column(String(1000))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
