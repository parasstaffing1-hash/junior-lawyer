from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.intelligence import (
    ContradictionSeverity,
    ContradictionStatus,
    FactStatus,
    FactType,
    ReviewItemType,
    ReviewPriority,
    ReviewStatus,
    SourceRelation,
    StatementKind,
)


class SourceRead(BaseModel):
    id: UUID
    document_id: UUID
    filename: str | None = None
    page_id: UUID | None
    page_number: int | None
    relation: SourceRelation = SourceRelation.SUPPORTS
    quote: str
    start_char: int | None
    end_char: int | None
    confidence: float


class FactRead(BaseModel):
    id: UUID
    matter_id: UUID
    fact_key: str
    fact_type: FactType
    category: str
    label: str
    value_text: str
    normalized_value: str
    confidence: float
    status: FactStatus
    metadata_json: dict
    sources: list[SourceRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FactUpdate(BaseModel):
    status: FactStatus


class TimelineSourceRead(BaseModel):
    id: UUID
    document_id: UUID
    filename: str | None = None
    page_id: UUID | None
    page_number: int | None
    quote: str
    start_char: int | None
    end_char: int | None
    confidence: float


class TimelineEventRead(BaseModel):
    id: UUID
    matter_id: UUID
    event_key: str
    event_type: str
    event_date: date
    title: str
    description: str
    confidence: float
    metadata_json: dict
    sources: list[TimelineSourceRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StatementRead(BaseModel):
    id: UUID
    matter_id: UUID
    document_id: UUID
    filename: str | None = None
    page_id: UUID | None
    page_number: int | None
    kind: StatementKind
    speaker_role: str | None
    raw_text: str
    normalized_text: str
    confidence: float
    start_char: int | None
    end_char: int | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContradictionValue(BaseModel):
    """One conflicting value behind a contradiction, as stored in values_json."""

    fact_id: str
    value: str
    display: str
    confidence: float


class ContradictionRead(BaseModel):
    id: UUID
    matter_id: UUID
    contradiction_key: str
    fact_key: str
    label: str
    explanation: str
    severity: ContradictionSeverity
    status: ContradictionStatus
    values_json: list[ContradictionValue]
    fact_ids_json: list[str]
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContradictionUpdate(BaseModel):
    status: ContradictionStatus


class ReviewItemRead(BaseModel):
    id: UUID
    matter_id: UUID
    item_type: ReviewItemType
    target_id: str
    title: str
    reason: str
    priority: ReviewPriority
    status: ReviewStatus
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewItemUpdate(BaseModel):
    status: ReviewStatus


class EvidenceFactRead(BaseModel):
    fact: FactRead
    contradiction_id: UUID | None = None
    contradiction_severity: ContradictionSeverity | None = None


class EvidenceMatrixRead(BaseModel):
    matter_id: UUID
    facts: list[EvidenceFactRead] = Field(default_factory=list)
    statement_counts: dict[str, int] = Field(default_factory=dict)


class IntelligenceSummaryRead(BaseModel):
    matter_id: UUID
    facts: int
    timeline_events: int
    claims: int
    admissions: int
    denials: int
    contradictions: int
    open_review_items: int
    source_documents: int
    source_pages: int


class RebuildResultRead(IntelligenceSummaryRead):
    rebuilt: bool = True
