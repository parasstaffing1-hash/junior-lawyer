from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.operations import (
    ChangeSeverity, CourtChangeType, CourtSourceKind, CourtTrackerStatus, NotificationChannel,
    NotificationStatus, WorkflowRunStatus, WorkflowTaskPriority, WorkflowTaskStatus,
    WorkflowTemplateStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkflowTemplateRead(ORMModel):
    id: UUID
    organization_id: UUID | None
    code: str
    name_en: str
    name_hi: str | None
    description: str | None
    version: int
    status: WorkflowTemplateStatus
    trigger_type: str
    conditions_json: dict
    actions_json: list
    source_label: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowEventRead(ORMModel):
    id: UUID
    matter_id: UUID | None
    event_type: str
    source_type: str | None
    source_id: UUID | None
    occurred_at: datetime
    payload_json: dict


class WorkflowTaskCreate(BaseModel):
    matter_id: UUID | None = None
    title: str = Field(min_length=2, max_length=350)
    description: str | None = None
    assigned_membership_id: UUID | None = None
    priority: WorkflowTaskPriority = WorkflowTaskPriority.MEDIUM
    due_at: datetime | None = None


class WorkflowTaskUpdate(BaseModel):
    status: WorkflowTaskStatus | None = None
    priority: WorkflowTaskPriority | None = None
    assigned_membership_id: UUID | None = None
    due_at: datetime | None = None


class WorkflowTaskRead(ORMModel):
    id: UUID
    organization_id: UUID
    matter_id: UUID | None
    workflow_run_id: UUID | None
    source_event_id: UUID | None
    assigned_membership_id: UUID | None
    title: str
    description: str | None
    status: WorkflowTaskStatus
    priority: WorkflowTaskPriority
    due_at: datetime | None
    completed_at: datetime | None
    escalation_level: int
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class WorkflowRunRead(ORMModel):
    id: UUID
    organization_id: UUID
    matter_id: UUID | None
    template_id: UUID
    trigger_event_id: UUID
    status: WorkflowRunStatus
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    output_json: dict


class NotificationRead(ORMModel):
    id: UUID
    matter_id: UUID | None
    task_id: UUID | None
    recipient_membership_id: UUID | None
    channel: NotificationChannel
    status: NotificationStatus
    subject: str
    body: str
    scheduled_at: datetime
    sent_at: datetime | None


class CourtTrackerCreate(BaseModel):
    matter_id: UUID
    source_kind: CourtSourceKind = CourtSourceKind.ECOURTS_MANUAL
    cnr_number: str | None = Field(default=None, max_length=32)
    case_number: str | None = Field(default=None, max_length=160)
    court_name: str | None = Field(default=None, max_length=300)
    bench_name: str | None = Field(default=None, max_length=300)
    source_url: str | None = None
    config_json: dict = Field(default_factory=dict)


class CourtTrackerRead(ORMModel):
    id: UUID
    organization_id: UUID
    matter_id: UUID
    source_kind: CourtSourceKind
    cnr_number: str | None
    case_number: str | None
    court_name: str | None
    bench_name: str | None
    source_url: str | None
    status: CourtTrackerStatus
    last_checked_at: datetime | None
    next_check_at: datetime | None
    config_json: dict
    created_at: datetime
    updated_at: datetime


class CourtSnapshotCreate(BaseModel):
    case_status: str | None = Field(default=None, max_length=160)
    stage: str | None = Field(default=None, max_length=240)
    next_hearing_date: date | None = None
    judge_or_bench: str | None = Field(default=None, max_length=300)
    order_count: int = Field(default=0, ge=0)
    latest_order_date: date | None = None
    latest_order_reference: str | None = Field(default=None, max_length=300)
    source_payload_json: dict = Field(default_factory=dict)
    captured_at: datetime | None = None


class CourtSnapshotRead(ORMModel):
    id: UUID
    tracker_id: UUID
    captured_at: datetime
    case_status: str | None
    stage: str | None
    next_hearing_date: date | None
    judge_or_bench: str | None
    order_count: int
    latest_order_date: date | None
    latest_order_reference: str | None
    content_hash: str
    source_payload_json: dict


class CourtChangeRead(ORMModel):
    id: UUID
    matter_id: UUID
    tracker_id: UUID
    previous_snapshot_id: UUID | None
    current_snapshot_id: UUID
    change_type: CourtChangeType
    severity: ChangeSeverity
    summary: str
    old_value: str | None
    new_value: str | None
    detected_at: datetime
    reviewed_at: datetime | None
    workflow_event_id: UUID | None


class SweepRequest(BaseModel):
    horizon_hours: int = Field(default=48, ge=1, le=720)
    escalate_overdue_hours: int = Field(default=24, ge=1, le=720)


class OperationsPreferenceRead(ORMModel):
    daily_agenda_enabled: bool
    daily_agenda_hour_local: int
    due_soon_hours: int
    overdue_escalation_hours: int
    channels_json: list


class OperationsPreferenceUpdate(BaseModel):
    daily_agenda_enabled: bool | None = None
    daily_agenda_hour_local: int | None = Field(default=None, ge=0, le=23)
    due_soon_hours: int | None = Field(default=None, ge=1, le=720)
    overdue_escalation_hours: int | None = Field(default=None, ge=1, le=720)
    channels_json: list[str] | None = None


class AgendaItem(BaseModel):
    kind: str
    id: UUID
    matter_id: UUID | None
    matter_title: str | None
    when: datetime | date | None
    title: str
    status: str
    priority: str | None = None
    requires_action: bool = True
    detail: str | None = None


class OperationsDashboard(BaseModel):
    open_tasks: int
    overdue_tasks: int
    upcoming_hearings: int
    unreviewed_court_changes: int
    pending_notifications: int
    active_trackers: int
    high_priority_items: int

class CourtSnapshotCaptureRead(BaseModel):
    snapshot: CourtSnapshotRead
    changes: list[CourtChangeRead]


class CourtSourceCapabilityRead(BaseModel):
    source_kind: CourtSourceKind
    automatic_fetch: bool
    requires_user_or_approved_connector: bool
    note: str
