from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.analytics import (
    AnalyticsGoalStatus,
    AnalyticsRiskSeverity,
    AnalyticsRiskStatus,
    AnalyticsScope,
    GoalComparison,
    MetricDirection,
    SnapshotKind,
)


class MetricDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    metric_key: str
    name_en: str
    name_hi: str | None
    description: str | None
    unit: str
    direction: MetricDirection
    formula_json: dict


class AnalyticsPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    rolling_window_days: int
    currency: str
    health_weights_json: dict
    thresholds_json: dict
    enable_risk_detection: bool
    show_financials_to_partners: bool
    metadata_json: dict


class AnalyticsPreferenceUpdate(BaseModel):
    rolling_window_days: int | None = Field(default=None, ge=7, le=365)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    health_weights_json: dict | None = None
    thresholds_json: dict | None = None
    enable_risk_detection: bool | None = None
    show_financials_to_partners: bool | None = None
    metadata_json: dict | None = None


class MatterHealthRead(BaseModel):
    matter_id: UUID
    title: str
    reference_number: str | None
    client_name: str | None
    score: int
    risk_level: str
    overdue_tasks: int
    high_priority_tasks: int
    deadlines_due_7d: int
    open_contradictions: int
    open_high_draft_findings: int
    unreviewed_court_changes: int
    open_evidence_gaps: int
    reasons: list[dict[str, Any]]


class TeamPerformanceRead(BaseModel):
    membership_id: UUID
    user_id: UUID
    name: str
    role: str
    open_tasks: int
    overdue_tasks: int
    high_priority_tasks: int
    completed_tasks_window: int
    billable_minutes_window: int
    submitted_minutes_window: int
    workload_score: int


class ClientHealthRead(BaseModel):
    client_id: UUID
    client_name: str
    outstanding_amount: float
    overdue_amount: float
    open_portal_requests: int
    active_matters: int
    last_communication_at: datetime | None
    health_score: int
    reasons: list[str]


class FinancialSummary(BaseModel):
    currency: str
    window_days: int | None = None
    outstanding_amount: float
    overdue_amount: float
    issued_window: float
    collected_window: float
    collection_rate: float
    ageing: dict[str, float]


class QualitySummary(BaseModel):
    draft_health_avg: float
    approved_drafts_window: int
    open_high_draft_findings: int
    contract_health_avg: float
    open_high_contract_risks: int
    approved_knowledge_assets: int
    knowledge_reuse: int
    window_days: int | None = None


class AnalyticsDashboard(BaseModel):
    active_matters: int
    matter_health_avg: float
    at_risk_matters: int
    overdue_tasks: int
    upcoming_hearings_7d: int
    deadlines_due_7d: int
    quality: QualitySummary
    financials: FinancialSummary | None
    formula_note: str


class SnapshotCreate(BaseModel):
    kind: SnapshotKind = SnapshotKind.MANUAL
    notes: str | None = Field(default=None, max_length=2000)


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    kind: SnapshotKind
    period_start: date
    period_end: date
    generated_by_membership_id: UUID | None
    payload_hash: str
    summary_json: dict
    notes: str | None
    created_at: datetime


class RiskSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    matter_id: UUID | None
    client_id: UUID | None
    membership_id: UUID | None
    signal_type: str
    severity: AnalyticsRiskSeverity
    status: AnalyticsRiskStatus
    title: str
    explanation: str
    metric_key: str | None
    observed_value: float | None
    threshold_value: float | None
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    metadata_json: dict


class RiskSignalUpdate(BaseModel):
    status: AnalyticsRiskStatus


class GoalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=300)
    metric_key: str = Field(min_length=2, max_length=180)
    scope_type: AnalyticsScope = AnalyticsScope.ORGANIZATION
    scope_id: UUID | None = None
    comparison: GoalComparison = GoalComparison.AT_LEAST
    target_value: float
    start_date: date
    end_date: date
    notes: str | None = Field(default=None, max_length=2000)


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    metric_key: str
    scope_type: AnalyticsScope
    scope_id: UUID | None
    comparison: GoalComparison
    target_value: float
    start_date: date
    end_date: date
    status: AnalyticsGoalStatus
    notes: str | None
    created_at: datetime


class GoalProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    goal_id: UUID
    recorded_at: datetime
    actual_value: float
    target_value: float
    progress_percent: float
    target_met: bool


class GoalWithProgress(BaseModel):
    goal: GoalRead
    progress: GoalProgressRead | None
