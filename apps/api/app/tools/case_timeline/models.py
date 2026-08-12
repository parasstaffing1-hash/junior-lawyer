from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TimelineImportance(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TimelineEventType(str, Enum):
    FACT = "fact"
    COMMUNICATION = "communication"
    FILING = "filing"
    HEARING = "hearing"
    ORDER = "order"
    PAYMENT = "payment"
    CONTRACT = "contract"
    NOTICE = "notice"
    EVIDENCE = "evidence"
    OTHER = "other"


class TimelineSourceReference(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    document_id: str | None = Field(default=None, max_length=160)
    page: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class TimelineEvent(BaseModel):
    event_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    event_type: TimelineEventType = TimelineEventType.FACT
    importance: TimelineImportance = TimelineImportance.NORMAL
    parties: list[str] = Field(default_factory=list, max_length=50)
    source_references: list[TimelineSourceReference] = Field(default_factory=list, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_dates(self) -> "TimelineEvent":
        has_exact = self.event_date is not None
        has_range = self.start_date is not None or self.end_date is not None
        if has_exact and has_range:
            raise ValueError("use event_date or start_date/end_date, not both")
        if not has_exact and self.start_date is None:
            raise ValueError("event_date or start_date is required")
        if self.end_date is not None and self.start_date is None:
            raise ValueError("start_date is required when end_date is supplied")
        if self.start_date is not None and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self


class CaseTimelineRequest(BaseModel):
    case_reference: str | None = Field(default=None, max_length=200)
    title: str = Field(default="Case Chronology", min_length=1, max_length=300)
    events: list[TimelineEvent] = Field(min_length=1, max_length=2000)
    include_day_gaps: bool = True


class RenderedTimelineEvent(BaseModel):
    sequence: int
    sort_date: date
    display_date: str
    start_date: date
    end_date: date | None
    title: str
    description: str | None
    event_type: TimelineEventType
    importance: TimelineImportance
    parties: list[str]
    source_references: list[TimelineSourceReference]
    tags: list[str]
    days_since_previous: int | None


class TimelineSummary(BaseModel):
    event_count: int
    first_date: date
    last_date: date
    span_days: int
    critical_count: int
    high_count: int
    events_with_sources: int


class CaseTimelineResponse(BaseModel):
    case_reference: str | None
    title: str
    events: list[RenderedTimelineEvent]
    summary: TimelineSummary
    markdown: str
    csv: str
    warnings: list[str]
    disclaimer: str
