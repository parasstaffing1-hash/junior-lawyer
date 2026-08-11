from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.contract import ContractRiskLevel, ContractRiskProfile, ContractType
from app.models.contract_review import (
    ClauseDeviationStatus,
    ContractReviewStatus,
    PlaybookRequirement,
    RedlineStatus,
    ReviewFindingStatus,
)


class PlaybookRuleRead(BaseModel):
    id: UUID
    code: str
    clause_type: str
    requirement: PlaybookRequirement
    preferred_variant: str
    risk_level: ContractRiskLevel
    guidance_en: str
    guidance_hi: str | None
    config_json: dict[str, Any]
    model_config = ConfigDict(from_attributes=True)


class PlaybookRead(BaseModel):
    id: UUID
    name: str
    owner_label: str
    contract_type: ContractType
    risk_profile: ContractRiskProfile
    active: bool
    settings_json: dict[str, Any]
    rules: list[PlaybookRuleRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class PlaybookRuleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=180)
    clause_type: str = Field(min_length=2, max_length=120)
    requirement: PlaybookRequirement = PlaybookRequirement.REQUIRED
    preferred_variant: str = Field(default="balanced", pattern="^(balanced|pro_party_a|pro_party_b)$")
    risk_level: ContractRiskLevel = ContractRiskLevel.MEDIUM
    guidance_en: str = ""
    guidance_hi: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)


class PlaybookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=240)
    owner_label: str = Field(default="Firm playbook", max_length=240)
    contract_type: ContractType
    risk_profile: ContractRiskProfile = ContractRiskProfile.BALANCED
    settings_json: dict[str, Any] = Field(default_factory=dict)
    rules: list[PlaybookRuleCreate] = Field(default_factory=list)


class ReviewClauseRead(BaseModel):
    id: UUID
    clause_type: str
    heading: str | None
    source_text: str
    position: int
    classification_confidence: float
    matched_template_id: UUID | None
    similarity: float
    deviation_status: ClauseDeviationStatus
    suggested_title_en: str | None
    suggested_title_hi: str | None
    suggested_body_en: str | None
    suggested_body_hi: str | None
    decision: str | None
    metadata_json: dict[str, Any]
    model_config = ConfigDict(from_attributes=True)


class ReviewFindingRead(BaseModel):
    id: UUID
    review_clause_id: UUID | None
    rule_code: str
    clause_type: str | None
    title: str
    explanation: str
    recommended_action: str
    level: ContractRiskLevel
    status: ReviewFindingStatus
    metadata_json: dict[str, Any]
    model_config = ConfigDict(from_attributes=True)


class RedlineRead(BaseModel):
    id: UUID
    version_number: int
    label: str
    status: RedlineStatus
    changes_json: list[dict[str, Any]]
    generated_filename: str
    sha256: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ContractReviewRead(BaseModel):
    id: UUID
    matter_id: UUID | None
    internal_contract_id: UUID | None
    playbook_id: UUID | None
    title: str
    counterparty_name: str | None
    contract_type: ContractType
    status: ContractReviewStatus
    source_format: str
    source_filename: str
    source_sha256: str
    language: str
    text_length: int
    health_score: int
    metadata_json: dict[str, Any]
    clauses: list[ReviewClauseRead] = Field(default_factory=list)
    findings: list[ReviewFindingRead] = Field(default_factory=list)
    redlines: list[RedlineRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ContractReviewListItem(BaseModel):
    id: UUID
    title: str
    counterparty_name: str | None
    contract_type: ContractType
    status: ContractReviewStatus
    language: str
    health_score: int
    clause_count: int
    open_high_risks: int
    source_filename: str
    updated_at: datetime


class FindingUpdate(BaseModel):
    status: ReviewFindingStatus


class ClauseDecisionUpdate(BaseModel):
    decision: str = Field(pattern="^(keep|replace|accept_risk|remove)$")


class ReviewStats(BaseModel):
    reviews: int
    clauses: int
    open_high_risks: int
    redlines: int
