from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class ValidationCampaignStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    HELD = "held"
    PASSED = "passed"
    APPROVED = "approved"


class ValidationScenarioKind(StrEnum):
    E2E = "e2e"
    SECURITY = "security"
    LOAD = "load"
    RECOVERY = "recovery"
    ACCESSIBILITY = "accessibility"
    DATA_INTEGRITY = "data_integrity"
    BILINGUAL = "bilingual"
    LARGE_DOCUMENT = "large_document"
    WORKERS = "workers"
    DEPLOYMENT = "deployment"


class ValidationExecutionMode(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    MANUAL = "manual"


class ValidationSeverity(StrEnum):
    ADVISORY = "advisory"
    REQUIRED = "required"
    CRITICAL = "critical"


class ValidationRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ValidationEvidenceKind(StrEnum):
    REPORT = "report"
    LOG = "log"
    HASH = "hash"
    SCREENSHOT = "screenshot"
    ARTIFACT = "artifact"
    ATTESTATION = "attestation"


class ReleaseCandidateStatus(StrEnum):
    DRAFT = "draft"
    HELD = "held"
    READY = "ready"
    APPROVED = "approved"


class PilotCheckStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"


class ValidationSignoffDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ValidationDatasetKind(StrEnum):
    SYNTHETIC_DOCUMENTS = "synthetic_documents"
    LARGE_PDF = "large_pdf"
    SEARCH_CORPUS = "search_corpus"
    BILINGUAL_CORPUS = "bilingual_corpus"
    SECURITY_FIXTURES = "security_fixtures"


class ValidationCampaign(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "validation_campaigns"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    release_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("release_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    environment_id: Mapped[UUID | None] = mapped_column(ForeignKey("deployment_environments.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(260))
    candidate_version: Mapped[str] = mapped_column(String(100), index=True)
    build_ref: Mapped[str | None] = mapped_column(String(180), nullable=True)
    status: Mapped[ValidationCampaignStatus] = mapped_column(String(30), default=ValidationCampaignStatus.DRAFT, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class ValidationScenario(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "validation_scenarios"
    __table_args__ = (UniqueConstraint("organization_id", "scenario_key", name="uq_validation_scenario_org_key"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    scenario_key: Mapped[str] = mapped_column(String(140), index=True)
    name: Mapped[str] = mapped_column(String(260))
    description: Mapped[str] = mapped_column(Text)
    kind: Mapped[ValidationScenarioKind] = mapped_column(String(40), index=True)
    execution_mode: Mapped[ValidationExecutionMode] = mapped_column(String(30), index=True)
    severity: Mapped[ValidationSeverity] = mapped_column(String(30), default=ValidationSeverity.REQUIRED, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    thresholds_json: Mapped[dict] = mapped_column(JSON, default=dict)
    instructions_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ValidationScenarioRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "validation_scenario_runs"
    __table_args__ = (UniqueConstraint("campaign_id", "scenario_id", name="uq_validation_campaign_scenario"),)

    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("validation_campaigns.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[UUID] = mapped_column(ForeignKey("validation_scenarios.id", ondelete="CASCADE"), index=True)
    status: Mapped[ValidationRunStatus] = mapped_column(String(30), default=ValidationRunStatus.PENDING, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class ValidationEvidence(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "validation_evidence"

    scenario_run_id: Mapped[UUID] = mapped_column(ForeignKey("validation_scenario_runs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[ValidationEvidenceKind] = mapped_column(String(30), index=True)
    label: Mapped[str] = mapped_column(String(300))
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ReleaseCandidateManifest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "release_candidate_manifests"
    __table_args__ = (UniqueConstraint("campaign_id", name="uq_release_candidate_campaign"),)

    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("validation_campaigns.id", ondelete="CASCADE"), index=True)
    release_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("release_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    environment_id: Mapped[UUID | None] = mapped_column(ForeignKey("deployment_environments.id", ondelete="SET NULL"), nullable=True, index=True)
    candidate_version: Mapped[str] = mapped_column(String(100), index=True)
    database_revision: Mapped[str | None] = mapped_column(String(180), nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[ReleaseCandidateStatus] = mapped_column(String(30), default=ReleaseCandidateStatus.DRAFT, index=True)
    gate_json: Mapped[dict] = mapped_column(JSON, default=dict)
    manifest_json: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)


class PilotReadinessCheck(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pilot_readiness_checks"
    __table_args__ = (UniqueConstraint("campaign_id", "check_key", name="uq_pilot_check_campaign_key"),)

    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("validation_campaigns.id", ondelete="CASCADE"), index=True)
    check_key: Mapped[str] = mapped_column(String(140), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(300))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[PilotCheckStatus] = mapped_column(String(30), default=PilotCheckStatus.PENDING, index=True)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ValidationSignoff(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "validation_signoffs"
    __table_args__ = (UniqueConstraint("campaign_id", "membership_id", name="uq_validation_signoff_campaign_member"),)

    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("validation_campaigns.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    decision: Mapped[ValidationSignoffDecision] = mapped_column(String(30), index=True)
    role_label: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ValidationDataset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "validation_datasets"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(ForeignKey("validation_campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[ValidationDatasetKind] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(260))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    generation_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
