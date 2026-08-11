from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.procedure import (
    ComplianceStatus,
    DayBasis,
    DeadlineAdjustment,
    DeadlineStatus,
    DirectionStatus,
    HearingStatus,
    MatterProcedureStatus,
    ProcedurePackStatus,
)


class ProcedureStepInput(BaseModel):
    code: str = Field(min_length=2, max_length=180)
    sequence: int = Field(ge=1)
    name_en: str = Field(min_length=2, max_length=300)
    name_hi: str | None = Field(default=None, max_length=300)
    description: str | None = None
    required: bool = True
    dependency_codes_json: list[str] = Field(default_factory=list)
    checklist_json: list[str] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DeadlineRuleInput(BaseModel):
    code: str = Field(min_length=2, max_length=180)
    name_en: str = Field(min_length=2, max_length=300)
    name_hi: str | None = Field(default=None, max_length=300)
    trigger_code: str = Field(min_length=2, max_length=180)
    offset_days: int = Field(ge=0, le=3650)
    day_basis: DayBasis = DayBasis.CALENDAR
    count_from_next_day: bool = True
    adjustment: DeadlineAdjustment = DeadlineAdjustment.NONE
    requires_lawyer_review: bool = True
    source_name: str | None = Field(default=None, max_length=350)
    source_url: str | None = Field(default=None, max_length=1000)
    source_citation: str | None = Field(default=None, max_length=500)
    effective_from: date | None = None
    effective_to: date | None = None
    verified: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ProcedurePackCreate(BaseModel):
    code: str = Field(min_length=2, max_length=180)
    name_en: str = Field(min_length=2, max_length=300)
    name_hi: str | None = Field(default=None, max_length=300)
    jurisdiction: str = Field(default="India", max_length=120)
    proceeding_type: str = Field(min_length=2, max_length=160)
    court_level: str | None = Field(default=None, max_length=120)
    description: str | None = None
    version: int = Field(default=1, ge=1)
    status: ProcedurePackStatus = ProcedurePackStatus.DRAFT
    effective_from: date | None = None
    effective_to: date | None = None
    source_name: str | None = Field(default=None, max_length=350)
    source_url: str | None = Field(default=None, max_length=1000)
    source_citation: str | None = Field(default=None, max_length=500)
    verified: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    steps: list[ProcedureStepInput] = Field(default_factory=list)
    deadline_rules: list[DeadlineRuleInput] = Field(default_factory=list)


class ProcedureStepRead(BaseModel):
    id: UUID
    code: str
    sequence: int
    name_en: str
    name_hi: str | None
    description: str | None
    required: bool
    dependency_codes_json: list[str]
    checklist_json: list[str]
    metadata_json: dict[str, Any]
    model_config = ConfigDict(from_attributes=True)


class DeadlineRuleRead(BaseModel):
    id: UUID
    code: str
    name_en: str
    name_hi: str | None
    trigger_code: str
    offset_days: int
    day_basis: DayBasis
    count_from_next_day: bool
    adjustment: DeadlineAdjustment
    requires_lawyer_review: bool
    source_name: str | None
    source_url: str | None
    source_citation: str | None
    effective_from: date | None
    effective_to: date | None
    verified: bool
    metadata_json: dict[str, Any]
    model_config = ConfigDict(from_attributes=True)


class ProcedurePackRead(BaseModel):
    id: UUID
    code: str
    name_en: str
    name_hi: str | None
    jurisdiction: str
    proceeding_type: str
    court_level: str | None
    description: str | None
    version: int
    status: ProcedurePackStatus
    effective_from: date | None
    effective_to: date | None
    source_name: str | None
    source_url: str | None
    source_citation: str | None
    verified: bool
    metadata_json: dict[str, Any]
    steps: list[ProcedureStepRead] = Field(default_factory=list)
    deadline_rules: list[DeadlineRuleRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class AttachProcedureRequest(BaseModel):
    pack_id: UUID
    started_on: date | None = None
    notes: str | None = None


class ComplianceRead(BaseModel):
    id: UUID
    procedure_step_id: UUID | None
    title: str
    description: str | None
    status: ComplianceStatus
    due_date: date | None
    assigned_to: str | None
    completed_at: datetime | None
    source_document_id: UUID | None
    notes: str | None
    metadata_json: dict[str, Any]
    model_config = ConfigDict(from_attributes=True)


class ComplianceUpdate(BaseModel):
    status: ComplianceStatus | None = None
    due_date: date | None = None
    assigned_to: str | None = Field(default=None, max_length=250)
    notes: str | None = None


class MatterProcedureRead(BaseModel):
    id: UUID
    matter_id: UUID
    pack_id: UUID
    pack_name: str
    pack_version: int
    status: MatterProcedureStatus
    started_on: date | None
    completed_on: date | None
    notes: str | None
    compliances: list[ComplianceRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DeadlineCalculationRequest(BaseModel):
    trigger_date: date
    offset_days: int = Field(ge=0, le=3650)
    day_basis: DayBasis = DayBasis.CALENDAR
    count_from_next_day: bool = True
    adjustment: DeadlineAdjustment = DeadlineAdjustment.NONE
    holidays: list[date] = Field(default_factory=list)


class DeadlineCalculationRead(BaseModel):
    trigger_date: date
    calculated_date: date
    due_date: date
    offset_days: int
    day_basis: DayBasis
    count_from_next_day: bool
    adjustment: DeadlineAdjustment
    skipped_weekends: int
    skipped_holidays: int
    adjustment_days: int


class MatterDeadlineCreate(DeadlineCalculationRequest):
    title: str = Field(min_length=2, max_length=350)
    matter_procedure_id: UUID | None = None
    trigger_type: str = Field(default="manual", max_length=120)
    trigger_id: str | None = Field(default=None, max_length=100)
    source_name: str | None = Field(default=None, max_length=350)
    source_url: str | None = Field(default=None, max_length=1000)
    source_citation: str | None = Field(default=None, max_length=500)
    notes: str | None = None


class RuleDeadlineCreate(BaseModel):
    deadline_rule_id: UUID
    trigger_date: date
    matter_procedure_id: UUID | None = None
    trigger_type: str = Field(default="rule", max_length=120)
    trigger_id: str | None = Field(default=None, max_length=100)
    holidays: list[date] = Field(default_factory=list)
    notes: str | None = None


class DeadlineRead(BaseModel):
    id: UUID
    matter_id: UUID
    matter_procedure_id: UUID | None
    deadline_rule_id: UUID | None
    title: str
    trigger_type: str
    trigger_id: str | None
    trigger_date: date
    calculated_date: date
    due_date: date
    status: DeadlineStatus
    reviewed_by_lawyer: bool
    completed_at: datetime | None
    calculation_json: dict[str, Any]
    authority_json: dict[str, Any]
    notes: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DeadlineUpdate(BaseModel):
    reviewed_by_lawyer: bool | None = None
    completed: bool | None = None
    due_date: date | None = None
    notes: str | None = None


class HearingCreate(BaseModel):
    matter_id: UUID
    scheduled_for: datetime
    court_name: str | None = Field(default=None, max_length=350)
    courtroom: str | None = Field(default=None, max_length=180)
    judge_or_bench: str | None = Field(default=None, max_length=350)
    purpose: str | None = Field(default=None, max_length=350)
    source_document_id: UUID | None = None
    source_url: str | None = Field(default=None, max_length=1000)
    notes: str | None = None


class HearingUpdate(BaseModel):
    scheduled_for: datetime | None = None
    court_name: str | None = Field(default=None, max_length=350)
    courtroom: str | None = Field(default=None, max_length=180)
    judge_or_bench: str | None = Field(default=None, max_length=350)
    purpose: str | None = Field(default=None, max_length=350)
    status: HearingStatus | None = None
    notes: str | None = None


class DirectionCreate(BaseModel):
    text: str = Field(min_length=3)
    due_date: date | None = None
    source_document_id: UUID | None = None
    page_number: int | None = Field(default=None, ge=1)
    requires_review: bool = True


class DirectionUpdate(BaseModel):
    status: DirectionStatus | None = None
    due_date: date | None = None
    requires_review: bool | None = None


class DirectionRead(BaseModel):
    id: UUID
    hearing_id: UUID
    matter_id: UUID
    text: str
    due_date: date | None
    status: DirectionStatus
    source_document_id: UUID | None
    page_number: int | None
    extracted: bool
    confidence: int
    requires_review: bool
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class HearingRead(BaseModel):
    id: UUID
    matter_id: UUID
    scheduled_for: datetime
    court_name: str | None
    courtroom: str | None
    judge_or_bench: str | None
    purpose: str | None
    status: HearingStatus
    source_document_id: UUID | None
    source_url: str | None
    notes: str | None
    metadata_json: dict[str, Any]
    directions: list[DirectionRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DirectionExtractionRequest(BaseModel):
    document_id: UUID
    order_date: date | None = None


class HearingBrief(BaseModel):
    matter_id: UUID
    matter_title: str
    hearing: HearingRead
    previous_hearing: HearingRead | None
    open_directions: list[DirectionRead]
    upcoming_deadlines: list[DeadlineRead]
    pending_compliances: list[dict[str, Any]]
    key_facts: list[dict[str, Any]]
    open_contradictions: list[dict[str, Any]]
    disclaimer: str


class AgendaItem(BaseModel):
    kind: str
    id: UUID
    matter_id: UUID
    title: str
    when: datetime
    status: str
    requires_review: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcedureStats(BaseModel):
    active_procedures: int
    pending_compliances: int
    upcoming_deadlines: int
    overdue_deadlines: int
    unreviewed_deadlines: int
    upcoming_hearings: int
    open_directions: int
