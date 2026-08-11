from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AnalyticsScope(StrEnum):
    ORGANIZATION = "organization"
    MATTER = "matter"
    MEMBER = "member"
    CLIENT = "client"


class MetricDirection(StrEnum):
    HIGHER_BETTER = "higher_better"
    LOWER_BETTER = "lower_better"
    NEUTRAL = "neutral"


class SnapshotKind(StrEnum):
    MANUAL = "manual"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AnalyticsRiskSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalyticsRiskStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AnalyticsGoalStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class GoalComparison(StrEnum):
    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    EXACT = "exact"


class AnalyticsMetricDefinition(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analytics_metric_definitions"
    __table_args__ = (UniqueConstraint("organization_id", "metric_key", name="uq_analytics_metric_org_key"),)

    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    metric_key: Mapped[str] = mapped_column(String(180), index=True)
    name_en: Mapped[str] = mapped_column(String(260))
    name_hi: Mapped[str | None] = mapped_column(String(260))
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(60), default="count")
    direction: Mapped[MetricDirection] = mapped_column(Enum(MetricDirection, native_enum=False), default=MetricDirection.NEUTRAL, index=True)
    formula_json: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class AnalyticsPreference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analytics_preferences"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_analytics_preferences_org"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    rolling_window_days: Mapped[int] = mapped_column(Integer, default=30)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    health_weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    thresholds_json: Mapped[dict] = mapped_column(JSON, default=dict)
    enable_risk_detection: Mapped[bool] = mapped_column(Boolean, default=True)
    show_financials_to_partners: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AnalyticsSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analytics_snapshots"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[SnapshotKind] = mapped_column(Enum(SnapshotKind, native_enum=False), default=SnapshotKind.MANUAL, index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    generated_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)


class AnalyticsMetricValue(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analytics_metric_values"
    __table_args__ = (UniqueConstraint("snapshot_id", "metric_key", "scope_type", "scope_id", name="uq_analytics_metric_value_scope"),)

    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), index=True)
    metric_key: Mapped[str] = mapped_column(String(180), index=True)
    scope_type: Mapped[AnalyticsScope] = mapped_column(Enum(AnalyticsScope, native_enum=False), index=True)
    scope_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_value: Mapped[str | None] = mapped_column(String(500))
    unit: Mapped[str] = mapped_column(String(60), default="count")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class MatterHealthSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_health_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_id", "matter_id", name="uq_matter_health_snapshot"),)

    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer, index=True)
    risk_level: Mapped[AnalyticsRiskSeverity] = mapped_column(Enum(AnalyticsRiskSeverity, native_enum=False), index=True)
    overdue_tasks: Mapped[int] = mapped_column(Integer, default=0)
    high_priority_tasks: Mapped[int] = mapped_column(Integer, default=0)
    deadlines_due_7d: Mapped[int] = mapped_column(Integer, default=0)
    open_contradictions: Mapped[int] = mapped_column(Integer, default=0)
    open_high_draft_findings: Mapped[int] = mapped_column(Integer, default=0)
    unreviewed_court_changes: Mapped[int] = mapped_column(Integer, default=0)
    open_evidence_gaps: Mapped[int] = mapped_column(Integer, default=0)
    reasons_json: Mapped[list] = mapped_column(JSON, default=list)


class MemberPerformanceSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "member_performance_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_id", "membership_id", name="uq_member_performance_snapshot"),)

    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    open_tasks: Mapped[int] = mapped_column(Integer, default=0)
    overdue_tasks: Mapped[int] = mapped_column(Integer, default=0)
    high_priority_tasks: Mapped[int] = mapped_column(Integer, default=0)
    completed_tasks_window: Mapped[int] = mapped_column(Integer, default=0)
    billable_minutes_window: Mapped[int] = mapped_column(Integer, default=0)
    submitted_minutes_window: Mapped[int] = mapped_column(Integer, default=0)
    workload_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ClientHealthSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_health_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_id", "client_id", name="uq_client_health_snapshot"),)

    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    outstanding_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    overdue_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    open_portal_requests: Mapped[int] = mapped_column(Integer, default=0)
    active_matters: Mapped[int] = mapped_column(Integer, default=0)
    last_communication_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    health_score: Mapped[int] = mapped_column(Integer, default=100, index=True)
    reasons_json: Mapped[list] = mapped_column(JSON, default=list)


class AnalyticsRiskSignal(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analytics_risk_signals"
    __table_args__ = (UniqueConstraint("organization_id", "dedupe_key", name="uq_analytics_risk_org_dedupe"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True)
    membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), nullable=True, index=True)
    signal_type: Mapped[str] = mapped_column(String(180), index=True)
    severity: Mapped[AnalyticsRiskSeverity] = mapped_column(Enum(AnalyticsRiskSeverity, native_enum=False), index=True)
    status: Mapped[AnalyticsRiskStatus] = mapped_column(Enum(AnalyticsRiskStatus, native_enum=False), default=AnalyticsRiskStatus.OPEN, index=True)
    title: Mapped[str] = mapped_column(String(350))
    explanation: Mapped[str] = mapped_column(Text)
    metric_key: Mapped[str | None] = mapped_column(String(180), index=True)
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(320), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AnalyticsGoal(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analytics_goals"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    metric_key: Mapped[str] = mapped_column(String(180), index=True)
    scope_type: Mapped[AnalyticsScope] = mapped_column(Enum(AnalyticsScope, native_enum=False), default=AnalyticsScope.ORGANIZATION, index=True)
    scope_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    comparison: Mapped[GoalComparison] = mapped_column(Enum(GoalComparison, native_enum=False), default=GoalComparison.AT_LEAST)
    target_value: Mapped[float] = mapped_column(Float)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[AnalyticsGoalStatus] = mapped_column(Enum(AnalyticsGoalStatus, native_enum=False), default=AnalyticsGoalStatus.ACTIVE, index=True)
    created_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)


class AnalyticsGoalProgress(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analytics_goal_progress"

    goal_id: Mapped[UUID] = mapped_column(ForeignKey("analytics_goals.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actual_value: Mapped[float] = mapped_column(Float)
    target_value: Mapped[float] = mapped_column(Float)
    progress_percent: Mapped[float] = mapped_column(Float)
    target_met: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
