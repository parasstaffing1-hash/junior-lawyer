from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class EvaluationCategory(StrEnum):
    OCR = "ocr"
    EXTRACTION = "extraction"
    LANGUAGE = "language"
    SEARCH = "search"
    CITATION = "citation"
    DRAFTING = "drafting"
    CONTRACT = "contract"
    DEADLINE = "deadline"
    SECURITY = "security"
    EVIDENCE = "evidence"
    CASE_LOOKUP = "case_lookup"
    REMEDY = "remedy"
    OTHER = "other"


class EvaluationCaseStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class EvaluationRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class EvaluationCaseRunStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class QAFindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class EvaluationSuite(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_suites"
    __table_args__ = (UniqueConstraint("organization_id", "suite_key", name="uq_evaluation_suite_org_key"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    suite_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(260))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    default_gate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EvaluationCase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_cases"
    __table_args__ = (UniqueConstraint("suite_id", "case_key", name="uq_evaluation_case_suite_key"),)

    suite_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_suites.id", ondelete="CASCADE"), index=True)
    case_key: Mapped[str] = mapped_column(String(180), index=True)
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[EvaluationCategory] = mapped_column(String(40), index=True)
    evaluator: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[EvaluationCaseStatus] = mapped_column(String(30), default=EvaluationCaseStatus.ACTIVE, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    critical: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EvaluationRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_runs"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    suite_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_suites.id", ondelete="CASCADE"), index=True)
    requested_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[EvaluationRunStatus] = mapped_column(String(30), default=EvaluationRunStatus.QUEUED, index=True)
    trigger: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    app_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    build_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0)
    skipped_cases: Mapped[int] = mapped_column(Integer, default=0)
    critical_failures: Mapped[int] = mapped_column(Integer, default=0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EvaluationCaseRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_case_runs"
    __table_args__ = (UniqueConstraint("run_id", "case_id", name="uq_evaluation_case_run_case"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_cases.id", ondelete="CASCADE"), index=True)
    status: Mapped[EvaluationCaseRunStatus] = mapped_column(String(30), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    actual_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_json: Mapped[dict] = mapped_column(JSON, default=dict)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvaluationMetric(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_metrics"
    __table_args__ = (UniqueConstraint("run_id", "metric_key", name="uq_evaluation_metric_run_key"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    metric_key: Mapped[str] = mapped_column(String(180), index=True)
    value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ReleaseQualityGate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "release_quality_gates"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    min_overall_score: Mapped[float] = mapped_column(Float, default=0.90)
    max_critical_failures: Mapped[int] = mapped_column(Integer, default=0)
    require_security_zero_failures: Mapped[bool] = mapped_column(Boolean, default=True)
    require_citation_zero_failures: Mapped[bool] = mapped_column(Boolean, default=True)
    category_thresholds_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ReleaseQualityGateRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "release_quality_gate_runs"

    gate_id: Mapped[UUID] = mapped_column(ForeignKey("release_quality_gates.id", ondelete="CASCADE"), index=True)
    evaluation_run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True)
    passed: Mapped[bool] = mapped_column(Boolean, index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reasons_json: Mapped[list] = mapped_column(JSON, default=list)
    category_scores_json: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)


class QAFinding(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "qa_findings"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True)
    case_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("evaluation_case_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[QAFindingSeverity] = mapped_column(String(30), index=True)
    code: Mapped[str] = mapped_column(String(120), index=True)
    message: Mapped[str] = mapped_column(Text)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class EvaluationBaseline(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evaluation_baselines"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_evaluation_baseline_org_name"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    suite_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_suites.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), index=True)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(220))
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)
