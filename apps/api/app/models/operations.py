from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class WorkflowTemplateStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"


class WorkflowRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowTaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class WorkflowTaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    CONSOLE = "console"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CourtSourceKind(StrEnum):
    MANUAL = "manual"
    ECOURTS_MANUAL = "ecourts_manual"
    OFFICIAL_IMPORT = "official_import"
    MOCK = "mock"


class CourtTrackerStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class CourtChangeType(StrEnum):
    NEW_ORDER = "new_order"
    HEARING_DATE_CHANGED = "hearing_date_changed"
    CASE_STATUS_CHANGED = "case_status_changed"
    STAGE_CHANGED = "stage_changed"
    JUDGE_CHANGED = "judge_changed"


class ChangeSeverity(StrEnum):
    INFO = "info"
    MEDIUM = "medium"
    HIGH = "high"


class WorkflowTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_templates"
    __table_args__ = (UniqueConstraint("organization_id", "code", "version", name="uq_workflow_template_org_code_version"),)

    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(160), index=True)
    name_en: Mapped[str] = mapped_column(String(300))
    name_hi: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    status: Mapped[WorkflowTemplateStatus] = mapped_column(Enum(WorkflowTemplateStatus, native_enum=False), default=WorkflowTemplateStatus.ACTIVE, index=True)
    trigger_type: Mapped[str] = mapped_column(String(160), index=True)
    conditions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    actions_json: Mapped[list] = mapped_column(JSON, default=list)
    source_label: Mapped[str | None] = mapped_column(String(300))


class WorkflowEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_events"
    __table_args__ = (UniqueConstraint("organization_id", "dedupe_key", name="uq_workflow_event_org_dedupe"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(160), index=True)
    source_type: Mapped[str | None] = mapped_column(String(120), index=True)
    source_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(300), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkflowRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_runs"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_templates.id", ondelete="RESTRICT"), index=True)
    trigger_event_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_events.id", ondelete="CASCADE"), index=True)
    status: Mapped[WorkflowRunStatus] = mapped_column(Enum(WorkflowRunStatus, native_enum=False), default=WorkflowRunStatus.RUNNING, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkflowTask(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_tasks"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    workflow_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    source_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflow_events.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(350), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[WorkflowTaskStatus] = mapped_column(Enum(WorkflowTaskStatus, native_enum=False), default=WorkflowTaskStatus.TODO, index=True)
    priority: Mapped[WorkflowTaskPriority] = mapped_column(Enum(WorkflowTaskPriority, native_enum=False), default=WorkflowTaskPriority.MEDIUM, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkflowNotification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_notifications"
    __table_args__ = (UniqueConstraint("organization_id", "dedupe_key", name="uq_workflow_notification_org_dedupe"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflow_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    recipient_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), nullable=True, index=True)
    channel: Mapped[NotificationChannel] = mapped_column(Enum(NotificationChannel, native_enum=False), default=NotificationChannel.IN_APP, index=True)
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus, native_enum=False), default=NotificationStatus.PENDING, index=True)
    subject: Mapped[str] = mapped_column(String(350))
    body: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(300), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text)


class WorkflowEscalation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_escalations"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_tasks.id", ondelete="CASCADE"), index=True)
    level: Mapped[int] = mapped_column(Integer, default=1, index=True)
    reason: Mapped[str] = mapped_column(String(500))
    escalated_to_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    escalated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)


class CourtCaseTracker(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "court_case_trackers"
    __table_args__ = (UniqueConstraint("matter_id", "source_kind", name="uq_court_tracker_matter_source"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    source_kind: Mapped[CourtSourceKind] = mapped_column(Enum(CourtSourceKind, native_enum=False), default=CourtSourceKind.MANUAL, index=True)
    cnr_number: Mapped[str | None] = mapped_column(String(32), index=True)
    case_number: Mapped[str | None] = mapped_column(String(160), index=True)
    court_name: Mapped[str | None] = mapped_column(String(300), index=True)
    bench_name: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CourtTrackerStatus] = mapped_column(Enum(CourtTrackerStatus, native_enum=False), default=CourtTrackerStatus.ACTIVE, index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)

    snapshots = relationship("CourtCaseSnapshot", back_populates="tracker", cascade="all, delete-orphan", lazy="selectin")


class CourtCaseSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "court_case_snapshots"

    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("court_case_trackers.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    case_status: Mapped[str | None] = mapped_column(String(160), index=True)
    stage: Mapped[str | None] = mapped_column(String(240), index=True)
    next_hearing_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    judge_or_bench: Mapped[str | None] = mapped_column(String(300))
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    latest_order_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    latest_order_reference: Mapped[str | None] = mapped_column(String(300))
    source_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    tracker = relationship("CourtCaseTracker", back_populates="snapshots")


class CourtCaseChange(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "court_case_changes"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("court_case_trackers.id", ondelete="CASCADE"), index=True)
    previous_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("court_case_snapshots.id", ondelete="SET NULL"), nullable=True)
    current_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("court_case_snapshots.id", ondelete="CASCADE"), index=True)
    change_type: Mapped[CourtChangeType] = mapped_column(Enum(CourtChangeType, native_enum=False), index=True)
    severity: Mapped[ChangeSeverity] = mapped_column(Enum(ChangeSeverity, native_enum=False), default=ChangeSeverity.INFO, index=True)
    summary: Mapped[str] = mapped_column(String(500))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    workflow_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflow_events.id", ondelete="SET NULL"), nullable=True, index=True)


class OperationsPreference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "operations_preferences"
    __table_args__ = (UniqueConstraint("membership_id", name="uq_operations_preference_membership"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    daily_agenda_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_agenda_hour_local: Mapped[int] = mapped_column(Integer, default=8)
    due_soon_hours: Mapped[int] = mapped_column(Integer, default=48)
    overdue_escalation_hours: Mapped[int] = mapped_column(Integer, default=24)
    channels_json: Mapped[list] = mapped_column(JSON, default=lambda: ["in_app"])
