from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.remedies import (
    RemedyAnalysisStatus,
    RemedyAuthorityType,
    RemedyCandidateStatus,
    RemedyMemoStatus,
    RemedyPackStatus,
)


class RemedyAuthorityInput(BaseModel):
    authority_type: RemedyAuthorityType
    statute_section_id: UUID | None = None
    judgment_id: UUID | None = None
    citation: str | None = Field(default=None, max_length=500)
    proposition: str = Field(min_length=3)
    source_url: str | None = None
    verified: bool = False


class RemedyRuleInput(BaseModel):
    code: str = Field(min_length=2, max_length=180)
    remedy_name_en: str = Field(min_length=2, max_length=300)
    remedy_name_hi: str | None = Field(default=None, max_length=300)
    description_en: str = Field(min_length=3)
    description_hi: str | None = None
    priority: int = Field(default=50, ge=0, le=100)
    case_stage_patterns_json: list[str] = Field(default_factory=list)
    status_patterns_json: list[str] = Field(default_factory=list)
    court_level_patterns_json: list[str] = Field(default_factory=list)
    order_type_patterns_json: list[str] = Field(default_factory=list)
    act_patterns_json: list[str] = Field(default_factory=list)
    section_patterns_json: list[str] = Field(default_factory=list)
    requires_final_order: bool = False
    requires_latest_order: bool = False
    forum_json: dict[str, Any] = Field(default_factory=dict)
    limitation_json: dict[str, Any] = Field(default_factory=dict)
    maintainability_json: dict[str, Any] = Field(default_factory=dict)
    required_documents_json: list[dict[str, Any] | str] = Field(default_factory=list)
    procedural_steps_json: list[str] = Field(default_factory=list)
    risks_json: list[str] = Field(default_factory=list)
    drafting_json: dict[str, Any] = Field(default_factory=dict)
    verified: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    authorities: list[RemedyAuthorityInput] = Field(default_factory=list)


class RemedyRulePackCreate(BaseModel):
    code: str = Field(min_length=2, max_length=180)
    name_en: str = Field(min_length=2, max_length=300)
    name_hi: str | None = Field(default=None, max_length=300)
    jurisdiction: str = Field(default="India", max_length=120)
    proceeding_type: str | None = Field(default=None, max_length=180)
    court_level: str | None = Field(default=None, max_length=120)
    version: int = Field(default=1, ge=1)
    status: RemedyPackStatus = RemedyPackStatus.DRAFT
    effective_from: date | None = None
    effective_to: date | None = None
    source_name: str | None = Field(default=None, max_length=350)
    source_url: str | None = None
    source_citation: str | None = Field(default=None, max_length=500)
    verified: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    rules: list[RemedyRuleInput] = Field(default_factory=list)


class RemedyAnalysisRequest(BaseModel):
    matter_id: UUID | None = None
    saved_case_id: UUID | None = None
    language: str = Field(default="en", pattern="^(en|hi|bilingual|hinglish)$")
    as_of_date: date | None = None


class RemedyAuthorityRead(BaseModel):
    id: UUID
    authority_type: RemedyAuthorityType
    statute_section_id: UUID | None
    judgment_id: UUID | None
    citation: str | None
    proposition: str
    source_url: str | None
    verified: bool
    model_config = ConfigDict(from_attributes=True)


class RemedyCandidateRead(BaseModel):
    id: UUID
    rule_id: UUID | None
    remedy_code: str
    remedy_name_en: str
    remedy_name_hi: str | None
    status: RemedyCandidateStatus
    applicability_score: int
    why_applicable_json: list[Any]
    forum_json: dict[str, Any]
    deadline_json: dict[str, Any]
    maintainability_json: dict[str, Any]
    required_documents_json: list[Any]
    procedural_steps_json: list[Any]
    risks_json: list[Any]
    drafting_json: dict[str, Any]
    lawyer_note: str | None
    reviewed_by_membership_id: UUID | None
    reviewed_at: datetime | None
    authorities: list[RemedyAuthorityRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class RemedyAnalysisRead(BaseModel):
    id: UUID
    organization_id: UUID
    matter_id: UUID | None
    saved_case_id: UUID | None
    language: str
    status: RemedyAnalysisStatus
    case_snapshot_json: dict[str, Any]
    context_json: dict[str, Any]
    disclaimer: str
    analyzed_at: datetime
    candidates: list[RemedyCandidateRead] = Field(default_factory=list)
    coverage_warnings: list[str] = Field(default_factory=list)


class RemedyCandidateReview(BaseModel):
    status: RemedyCandidateStatus | None = None
    lawyer_note: str | None = None


class RemedyMemoCreate(BaseModel):
    language: str = Field(default="en", pattern="^(en|hi|bilingual)$")


class RemedyMemoRead(BaseModel):
    id: UUID
    candidate_id: UUID
    language: str
    status: RemedyMemoStatus
    content: str
    source_snapshot_json: dict[str, Any]
    generated_deterministically: bool
    ai_run_id: UUID | None
    reviewed_by_membership_id: UUID | None
    reviewed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class RemedyDraftCreate(BaseModel):
    requested_document_kind: str = Field(min_length=2, max_length=180)
    language: str = Field(default="en", pattern="^(en|hi|bilingual)$")
    relief_requested: str | None = None
    additional_instructions: str | None = None


class RemedyDraftLinkRead(BaseModel):
    id: UUID
    candidate_id: UUID
    legal_draft_id: UUID
    requested_document_kind: str
    model_config = ConfigDict(from_attributes=True)
