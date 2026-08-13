from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.contract import (
    ClauseSource,
    ContractLanguage,
    ContractRiskLevel,
    ContractRiskProfile,
    ContractRiskStatus,
    ContractStatus,
    ContractType,
)


class ContractQuestion(BaseModel):
    """One field of a contract questionnaire, as built by catalog.question()."""

    key: str
    label_en: str
    label_hi: str
    kind: str
    required: bool
    placeholder: str | None = None
    options: list[dict[str, str]] = Field(default_factory=list)
    default: Any = None


class ContractCatalogItem(BaseModel):
    contract_type: ContractType
    name_en: str
    name_hi: str
    description: str
    required_fields: list[str] = Field(default_factory=list)


class ContractQuestionnaire(BaseModel):
    contract_type: ContractType
    name_en: str
    name_hi: str
    description: str
    questions: list[ContractQuestion]
    default_clauses: list[str]


class ContractCreate(BaseModel):
    matter_id: UUID | None = None
    title: str = Field(min_length=2, max_length=350)
    contract_type: ContractType
    language: ContractLanguage = ContractLanguage.ENGLISH
    risk_profile: ContractRiskProfile = ContractRiskProfile.BALANCED
    jurisdiction: str = Field(default="India", max_length=120)
    governing_state: str | None = Field(default=None, max_length=120)
    party_a_name: str = Field(min_length=1, max_length=300)
    party_b_name: str = Field(min_length=1, max_length=300)
    effective_date: date | None = None
    questionnaire_json: dict[str, Any] = Field(default_factory=dict)


class ContractUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=350)
    language: ContractLanguage | None = None
    risk_profile: ContractRiskProfile | None = None
    jurisdiction: str | None = Field(default=None, max_length=120)
    governing_state: str | None = Field(default=None, max_length=120)
    party_a_name: str | None = Field(default=None, min_length=1, max_length=300)
    party_b_name: str | None = Field(default=None, min_length=1, max_length=300)
    effective_date: date | None = None
    questionnaire_json: dict[str, Any] | None = None


class ClauseRead(BaseModel):
    id: UUID
    clause_template_id: UUID | None
    clause_code: str
    clause_type: str
    variant_key: str
    title_en: str
    title_hi: str | None
    body_en: str
    body_hi: str | None
    position: int
    source: ClauseSource
    is_modified: bool
    metadata_json: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class ClauseUpdate(BaseModel):
    title_en: str | None = Field(default=None, max_length=300)
    title_hi: str | None = Field(default=None, max_length=300)
    body_en: str | None = None
    body_hi: str | None = None
    position: int | None = Field(default=None, ge=1)


class RiskRead(BaseModel):
    id: UUID
    rule_code: str
    clause_type: str | None
    title: str
    explanation: str
    level: ContractRiskLevel
    status: ContractRiskStatus
    metadata_json: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class RiskUpdate(BaseModel):
    status: ContractRiskStatus


class ContractRead(BaseModel):
    id: UUID
    matter_id: UUID | None
    title: str
    contract_type: ContractType
    language: ContractLanguage
    status: ContractStatus
    risk_profile: ContractRiskProfile
    jurisdiction: str
    governing_state: str | None
    party_a_name: str
    party_b_name: str
    effective_date: date | None
    questionnaire_json: dict[str, Any]
    health_score: int
    generated_filename: str | None
    approved_at: datetime | None
    metadata_json: dict[str, Any]
    clauses: list[ClauseRead] = Field(default_factory=list)
    risks: list[RiskRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractListItem(BaseModel):
    id: UUID
    title: str
    contract_type: ContractType
    language: ContractLanguage
    status: ContractStatus
    risk_profile: ContractRiskProfile
    party_a_name: str
    party_b_name: str
    health_score: int
    clause_count: int
    open_high_risks: int
    updated_at: datetime


class ContractVersionRead(BaseModel):
    id: UUID
    version_number: int
    label: str
    health_score: int
    sha256: str | None
    generated_filename: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DraftResult(BaseModel):
    contract: ContractRead
    version: ContractVersionRead


class ClauseLibraryRead(BaseModel):
    id: UUID
    code: str
    clause_type: str
    variant_key: str
    title_en: str
    title_hi: str | None
    contract_types_json: list[str]
    variables_json: list[str]
    version: int
    active: bool

    model_config = ConfigDict(from_attributes=True)


class ComparisonClause(BaseModel):
    clause_type: str
    status: str
    similarity: float
    left_title: str | None = None
    right_title: str | None = None
    left_text: str | None = None
    right_text: str | None = None


class ContractComparison(BaseModel):
    left_contract_id: UUID
    right_contract_id: UUID
    summary: dict[str, int]
    clauses: list[ComparisonClause]
