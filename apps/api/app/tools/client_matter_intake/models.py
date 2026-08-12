from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class IntakeFieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    NUMBER = "number"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    MULTICHOICE = "multichoice"


class ConflictPartyRole(str, Enum):
    CLIENT = "client"
    PROSPECTIVE_CLIENT = "prospective_client"
    ADVERSE_PARTY = "adverse_party"
    COUNTERPARTY = "counterparty"
    RELATED_PARTY = "related_party"
    WITNESS = "witness"
    OTHER = "other"


class MatchCondition(BaseModel):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    values: list[str] = Field(min_length=1, max_length=50)


class IntakeSectionDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=600)


class IntakeFieldDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=180)
    section: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    field_type: IntakeFieldType = IntakeFieldType.TEXT
    required: bool = False
    allowed_values: list[str] = Field(default_factory=list, max_length=100)
    max_length: int = Field(default=1000, ge=1, le=20_000)
    pattern: str | None = Field(default=None, max_length=500)
    placeholder: str | None = Field(default=None, max_length=240)
    help_text: str | None = Field(default=None, max_length=1000)
    include_in_conflict_terms: bool = False
    applies_if_all: list[MatchCondition] = Field(default_factory=list)
    applies_if_any: list[MatchCondition] = Field(default_factory=list)
    required_if_all: list[MatchCondition] = Field(default_factory=list)
    required_if_any: list[MatchCondition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_choices(self) -> "IntakeFieldDefinition":
        if self.field_type in {IntakeFieldType.CHOICE, IntakeFieldType.MULTICHOICE}:
            if not self.allowed_values:
                raise ValueError("choice fields must define allowed_values")
        normalized = [value.strip().lower() for value in self.allowed_values if value.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed_values must be unique ignoring case")
        return self


class ConsentDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=180)
    text: str = Field(min_length=1, max_length=3000)
    required: bool = True
    applies_if_all: list[MatchCondition] = Field(default_factory=list)
    applies_if_any: list[MatchCondition] = Field(default_factory=list)


class ConflictRequirementDefinition(BaseModel):
    description: str = Field(min_length=1, max_length=600)
    min_parties: int = Field(ge=1, le=100)
    applies_if_all: list[MatchCondition] = Field(default_factory=list)
    applies_if_any: list[MatchCondition] = Field(default_factory=list)


class IntakeTemplate(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=240)
    matter_type: str = Field(min_length=1, max_length=120)
    client_type: str = Field(min_length=1, max_length=120)
    jurisdiction: str = Field(min_length=1, max_length=160)
    effective_from: date
    effective_to: date | None = None
    sections: list[IntakeSectionDefinition] = Field(min_length=1, max_length=30)
    fields: list[IntakeFieldDefinition] = Field(min_length=1, max_length=250)
    consents: list[ConsentDefinition] = Field(default_factory=list, max_length=50)
    conflict_requirements: list[ConflictRequirementDefinition] = Field(default_factory=list, max_length=20)
    source_note: str = Field(min_length=1, max_length=1200)

    @model_validator(mode="after")
    def validate_template(self) -> "IntakeTemplate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")

        section_keys = [section.key for section in self.sections]
        if len(section_keys) != len(set(section_keys)):
            raise ValueError("section keys must be unique")
        known_sections = set(section_keys)

        field_keys = [field.key for field in self.fields]
        if len(field_keys) != len(set(field_keys)):
            raise ValueError("field keys must be unique")
        known_fields = set(field_keys)

        for field in self.fields:
            if field.section not in known_sections:
                raise ValueError(f"field '{field.key}' references unknown section '{field.section}'")
            for condition in (
                field.applies_if_all
                + field.applies_if_any
                + field.required_if_all
                + field.required_if_any
            ):
                if condition.field not in known_fields:
                    raise ValueError(
                        f"field '{field.key}' references unknown condition field '{condition.field}'"
                    )

        consent_keys = [consent.key for consent in self.consents]
        if len(consent_keys) != len(set(consent_keys)):
            raise ValueError("consent keys must be unique")
        for consent in self.consents:
            for condition in consent.applies_if_all + consent.applies_if_any:
                if condition.field not in known_fields:
                    raise ValueError(
                        f"consent '{consent.key}' references unknown condition field '{condition.field}'"
                    )

        for requirement in self.conflict_requirements:
            for condition in requirement.applies_if_all + requirement.applies_if_any:
                if condition.field not in known_fields:
                    raise ValueError(
                        f"conflict requirement references unknown condition field '{condition.field}'"
                    )
        return self


class IntakeTemplateSummary(BaseModel):
    id: str
    version: str
    title: str
    matter_type: str
    client_type: str
    jurisdiction: str
    effective_from: date
    effective_to: date | None
    sections: list[IntakeSectionDefinition]
    fields: list[IntakeFieldDefinition]
    consents: list[ConsentDefinition]
    source_note: str


class ConflictPartyInput(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    role: ConflictPartyRole
    organization: str | None = Field(default=None, max_length=300)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    notes: str | None = Field(default=None, max_length=1500)

    @model_validator(mode="after")
    def validate_aliases(self) -> "ConflictPartyInput":
        normalized = [alias.strip().lower() for alias in self.aliases if alias.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("aliases must be unique ignoring case")
        return self


class ConsentInput(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=80)
    accepted: bool
    accepted_at: datetime | None = None


class ClientMatterIntakeRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=120)
    intake_date: date
    values: dict[str, Any] = Field(default_factory=dict)
    conflict_parties: list[ConflictPartyInput] = Field(default_factory=list, max_length=200)
    consents: list[ConsentInput] = Field(default_factory=list, max_length=50)


class EvaluatedIntakeField(BaseModel):
    sequence: int
    key: str
    label: str
    section: str
    field_type: IntakeFieldType
    applicable: bool
    required: bool
    provided: bool
    valid: bool
    normalized_value: Any | None = None
    validation_messages: list[str]
    help_text: str | None


class EvaluatedConsent(BaseModel):
    key: str
    label: str
    text: str
    applicable: bool
    required: bool
    accepted: bool
    accepted_at: datetime | None


class NormalizedConflictParty(BaseModel):
    name: str
    role: ConflictPartyRole
    organization: str | None
    aliases: list[str]
    notes: str | None


class IntakeSummary(BaseModel):
    total_fields: int
    applicable_fields: int
    required_fields: int
    valid_provided_fields: int
    invalid_fields: int
    missing_required_fields: list[str]
    required_consents: int
    accepted_required_consents: int
    missing_required_consents: list[str]
    conflict_parties: int
    conflict_search_terms: int
    completion_percent: float
    required_completion_percent: float
    ready_for_review: bool


class ClientMatterIntakeResponse(BaseModel):
    template_id: str
    template_version: str
    title: str
    matter_type: str
    client_type: str
    jurisdiction: str
    intake_date: date
    fields: list[EvaluatedIntakeField]
    normalized_values: dict[str, Any]
    conflict_parties: list[NormalizedConflictParty]
    conflict_search_terms: list[str]
    consents: list[EvaluatedConsent]
    summary: IntakeSummary
    warnings: list[str]
    markdown: str
    audit_hash_sha256: str
    source_note: str
    disclaimer: str
