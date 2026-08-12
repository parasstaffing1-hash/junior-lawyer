from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ChecklistItemKind(str, Enum):
    DOCUMENT = "document"
    TASK = "task"
    INFORMATION = "information"


class RequirementLevel(str, Enum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class ItemStatus(str, Enum):
    PRESENT = "present"
    COMPLETED = "completed"
    PENDING = "pending"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class ContextFieldDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    required: bool = False
    allowed_values: list[str] = Field(default_factory=list, max_length=50)
    help_text: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_allowed_values(self) -> "ContextFieldDefinition":
        normalized = [value.strip().lower() for value in self.allowed_values if value.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed_values must be unique ignoring case")
        return self


class MatchCondition(BaseModel):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    values: list[str] = Field(min_length=1, max_length=50)


class ChecklistItemDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    category: str = Field(min_length=1, max_length=120)
    kind: ChecklistItemKind = ChecklistItemKind.DOCUMENT
    description: str | None = Field(default=None, max_length=1500)
    requirement: RequirementLevel = RequirementLevel.REQUIRED
    applies_if_all: list[MatchCondition] = Field(default_factory=list)
    applies_if_any: list[MatchCondition] = Field(default_factory=list)
    required_if_all: list[MatchCondition] = Field(default_factory=list)
    required_if_any: list[MatchCondition] = Field(default_factory=list)
    evidence_hint: str | None = Field(default=None, max_length=500)


class LegalChecklistTemplate(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=240)
    matter_type: str = Field(min_length=1, max_length=120)
    jurisdiction: str = Field(min_length=1, max_length=160)
    effective_from: date
    effective_to: date | None = None
    context_fields: list[ContextFieldDefinition] = Field(default_factory=list)
    items: list[ChecklistItemDefinition] = Field(min_length=1, max_length=250)
    source_note: str = Field(min_length=1, max_length=1200)

    @model_validator(mode="after")
    def validate_template(self) -> "LegalChecklistTemplate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")

        context_keys = [field.key for field in self.context_fields]
        if len(context_keys) != len(set(context_keys)):
            raise ValueError("context field keys must be unique")

        item_keys = [item.key for item in self.items]
        if len(item_keys) != len(set(item_keys)):
            raise ValueError("checklist item keys must be unique")

        known_context = set(context_keys)
        for item in self.items:
            for condition in (
                item.applies_if_all
                + item.applies_if_any
                + item.required_if_all
                + item.required_if_any
            ):
                if condition.field not in known_context:
                    raise ValueError(
                        f"item '{item.key}' references unknown context field '{condition.field}'"
                    )
        return self


class ChecklistTemplateSummary(BaseModel):
    id: str
    version: str
    title: str
    matter_type: str
    jurisdiction: str
    effective_from: date
    effective_to: date | None
    context_fields: list[ContextFieldDefinition]
    item_count: int
    source_note: str


class ChecklistItemInput(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=100)
    status: ItemStatus
    file_reference: str | None = Field(default=None, max_length=1000)
    document_date: date | None = None
    notes: str | None = Field(default=None, max_length=3000)


class LegalChecklistRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=120)
    assessment_date: date
    context: dict[str, str] = Field(default_factory=dict)
    items: list[ChecklistItemInput] = Field(default_factory=list, max_length=250)


class EvaluatedChecklistItem(BaseModel):
    sequence: int
    key: str
    title: str
    category: str
    kind: ChecklistItemKind
    description: str | None
    applicable: bool
    requirement: RequirementLevel
    required: bool
    status: ItemStatus
    satisfied: bool
    file_reference: str | None
    document_date: date | None
    notes: str | None
    evidence_hint: str | None
    reasons: list[str]


class ChecklistSummary(BaseModel):
    total_items: int
    applicable_items: int
    required_items: int
    required_satisfied: int
    required_outstanding: int
    recommended_items: int
    completed_applicable_items: int
    completion_percent: float
    required_completion_percent: float
    category_counts: dict[str, int]
    outstanding_required_keys: list[str]


class LegalChecklistResponse(BaseModel):
    template_id: str
    template_version: str
    title: str
    matter_type: str
    jurisdiction: str
    assessment_date: date
    context_used: dict[str, str]
    items: list[EvaluatedChecklistItem]
    summary: ChecklistSummary
    warnings: list[str]
    markdown: str
    source_note: str
    disclaimer: str
