from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.drafting import (
    DraftFindingLevel,
    DraftFindingStatus,
    DraftSectionSource,
    DraftSourceType,
    LegalDraftLanguage,
    LegalDraftStatus,
    LegalDraftType,
)


class AuthorityReference(BaseModel):
    source_type: DraftSourceType
    source_id: UUID


class LegalDraftCreate(BaseModel):
    matter_id: UUID
    draft_type: LegalDraftType
    language: LegalDraftLanguage = LegalDraftLanguage.ENGLISH
    title: str | None = Field(default=None, max_length=400)
    questionnaire_json: dict[str, Any] = Field(default_factory=dict)
    selected_fact_ids: list[UUID] = Field(default_factory=list)
    selected_timeline_event_ids: list[UUID] = Field(default_factory=list)
    authority_refs: list[AuthorityReference] = Field(default_factory=list)


class LegalDraftUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=400)
    language: LegalDraftLanguage | None = None
    questionnaire_json: dict[str, Any] | None = None


class DraftSourceRead(BaseModel):
    id: UUID
    source_type: DraftSourceType
    source_id: UUID | None
    label: str
    locator: str | None
    excerpt: str | None
    verified: bool
    metadata_json: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class DraftSectionRead(BaseModel):
    id: UUID
    section_key: str
    title_en: str
    title_hi: str | None
    body_en: str
    body_hi: str | None
    position: int
    source: DraftSectionSource
    reviewed: bool
    locked: bool
    metadata_json: dict[str, Any]
    sources: list[DraftSourceRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DraftSectionUpdate(BaseModel):
    title_en: str | None = Field(default=None, max_length=350)
    title_hi: str | None = Field(default=None, max_length=350)
    body_en: str | None = None
    body_hi: str | None = None
    position: int | None = Field(default=None, ge=1)
    reviewed: bool | None = None
    locked: bool | None = None


class DraftFindingRead(BaseModel):
    id: UUID
    rule_code: str
    section_key: str | None
    title: str
    explanation: str
    level: DraftFindingLevel
    status: DraftFindingStatus
    metadata_json: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class DraftFindingUpdate(BaseModel):
    status: DraftFindingStatus


class LegalDraftRead(BaseModel):
    id: UUID
    matter_id: UUID
    template_id: UUID | None
    title: str
    draft_type: LegalDraftType
    language: LegalDraftLanguage
    status: LegalDraftStatus
    court_name: str | None
    case_number: str | None
    questionnaire_json: dict[str, Any]
    health_score: int
    generated_filename: str | None
    approved_at: datetime | None
    metadata_json: dict[str, Any]
    sections: list[DraftSectionRead] = Field(default_factory=list)
    findings: list[DraftFindingRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LegalDraftListItem(BaseModel):
    id: UUID
    matter_id: UUID
    matter_title: str
    title: str
    draft_type: LegalDraftType
    language: LegalDraftLanguage
    status: LegalDraftStatus
    health_score: int
    open_high_findings: int
    reviewed_sections: int
    section_count: int
    updated_at: datetime


class LegalDraftVersionRead(BaseModel):
    id: UUID
    version_number: int
    label: str
    health_score: int
    sha256: str | None
    generated_filename: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DraftRenderResult(BaseModel):
    draft: LegalDraftRead
    version: LegalDraftVersionRead


class DraftTemplateRead(BaseModel):
    id: UUID
    code: str
    draft_type: LegalDraftType
    name_en: str
    name_hi: str | None
    description: str | None
    structure_json: list[dict[str, Any]]
    questions_json: list[dict[str, Any]]
    version: int
    active: bool

    model_config = ConfigDict(from_attributes=True)


class DraftContextPreview(BaseModel):
    matter_id: UUID
    matter_title: str
    court_name: str | None
    case_number: str | None
    available_facts: int
    safe_facts: int
    excluded_conflicting_facts: int
    timeline_events: int
    documents: int
    admissions: int
    denials: int
    open_contradictions: int
