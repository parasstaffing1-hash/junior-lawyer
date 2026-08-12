from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class DateKind(str, Enum):
    EFFECTIVE = "effective_date"
    EXECUTION = "execution_date"
    COMMENCEMENT = "commencement_date"
    EXPIRY = "expiry_date"
    RENEWAL = "renewal_date"
    PAYMENT_DUE = "payment_due"
    NOTICE_DEADLINE = "notice_deadline"
    TERMINATION = "termination_date"
    DELIVERY = "delivery_date"
    REPORTING = "reporting_date"
    OTHER = "other"


class RelativeUnit(str, Enum):
    BUSINESS_DAYS = "business_days"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


class DateRelation(str, Enum):
    ON = "on"
    BY = "by"
    WITHIN = "within"
    BEFORE = "before"
    AFTER = "after"
    FROM = "from"


class ObligationType(str, Enum):
    PAYMENT = "payment"
    NOTICE = "notice"
    DELIVERY = "delivery"
    REPORTING = "reporting"
    INSURANCE = "insurance"
    CONFIDENTIALITY = "confidentiality"
    RENEWAL = "renewal"
    AUDIT = "audit"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    OTHER = "other"


class Frequency(str, Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    CONTINUOUS = "continuous"
    EVENT_BASED = "event_based"
    UNKNOWN = "unknown"


class ExtractOptions(BaseModel):
    date_kinds: list[DateKind] | None = None
    obligation_types: list[ObligationType] | None = None
    include_other_dates: bool = False
    include_other_obligations: bool = False
    deduplicate: bool = True
    context_chars: int = Field(default=140, ge=40, le=500)
    max_dates: int = Field(default=500, ge=1, le=2_000)
    max_obligations: int = Field(default=500, ge=1, le=2_000)

    @model_validator(mode="after")
    def normalize_filters(self) -> "ExtractOptions":
        if self.date_kinds:
            self.date_kinds = list(dict.fromkeys(self.date_kinds))
        if self.obligation_types:
            self.obligation_types = list(dict.fromkeys(self.obligation_types))
        return self


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)
    options: ExtractOptions = Field(default_factory=ExtractOptions)


class ExtractionSignal(BaseModel):
    kind: str
    value: str


class ExtractedDate(BaseModel):
    date_kind: DateKind
    raw_text: str
    normalized_date: date | None = None
    relation: DateRelation | None = None
    relative_value: int | None = Field(default=None, ge=0)
    relative_unit: RelativeUnit | None = None
    anchor: str | None = None
    context: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    signals: list[ExtractionSignal] = Field(default_factory=list)


class ExtractedObligation(BaseModel):
    obligation_type: ObligationType
    actor: str | None = None
    action: str
    frequency: Frequency
    deadline_expression: str | None = None
    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    signals: list[ExtractionSignal] = Field(default_factory=list)


class ExtractionSummary(BaseModel):
    dates_returned: int
    obligations_returned: int
    absolute_dates: int
    relative_dates: int
    date_kind_counts: dict[str, int]
    obligation_type_counts: dict[str, int]


class SupportedPatternsResponse(BaseModel):
    absolute_date_formats: list[str]
    relative_deadline_examples: list[str]
    obligation_markers: list[str]
    disclaimer: str


class ExtractResponse(BaseModel):
    dates: list[ExtractedDate]
    obligations: list[ExtractedObligation]
    summary: ExtractionSummary
    warnings: list[str]
    disclaimer: str
