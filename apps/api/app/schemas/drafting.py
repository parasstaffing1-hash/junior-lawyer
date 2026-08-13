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


class DraftQuestion(BaseModel):
    """One questionnaire field, as built by drafting catalog.q()."""

    key: str
    label_en: str
    label_hi: str
    required: bool
    kind: str


class DraftSectionDefinition(BaseModel):
    key: str
    title_en: str
    title_hi: str


class DraftCatalogItem(BaseModel):
    draft_type: str
    name_en: str
    name_hi: str
    description: str
    section_count: int
    questions: list[DraftQuestion]


class DraftQuestionnaire(BaseModel):
    draft_type: str
    name_en: str
    name_hi: str
    description: str
    questions: list[DraftQuestion]
    sections: list[DraftSectionDefinition]


class TemplateSeedResult(BaseModel):
    created: int


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


class DraftLibraryItem(BaseModel):
    """One instrument in the drafting library."""

    code: str
    draft_type: str
    category: str
    category_name_en: str
    category_name_hi: str
    forum: str
    name_en: str
    name_hi: str
    description: str
    authority: str | None = None
    section_count: int
    question_count: int
    # False until a qualified advocate signs the template off for a named
    # jurisdiction. Shown in the UI rather than hidden.
    verified: bool


class DraftLibraryCategory(BaseModel):
    key: str
    name_en: str
    name_hi: str
    template_count: int


class DraftLibrary(BaseModel):
    categories: list[DraftLibraryCategory]
    templates: list[DraftLibraryItem]
    total: int


class DraftSendRequest(BaseModel):
    """Dispatch an approved draft by email."""

    to: list[str] = Field(min_length=1, max_length=25)
    # Recorded because a notice to an opposite party and a copy to one's own
    # client are different acts, and the file should say which happened.
    recipient_kind: str = Field(pattern="^(client|opposite_party|court|other)$")
    subject: str | None = Field(default=None, max_length=300)
    covering_note: str | None = Field(default=None, max_length=5000)
    cc: list[str] = Field(default_factory=list, max_length=25)
    bcc: list[str] = Field(default_factory=list, max_length=25)
    reply_to: str | None = Field(default=None, max_length=320)
    connection_id: UUID | None = None
    # Explicit acknowledgement of the recipient list. A mis-addressed legal
    # notice cannot be recalled.
    confirm: bool = False


class DraftSendResult(BaseModel):
    draft_id: str
    recipient_kind: str
    recipients: list[str]
    message_id: str | None = None
    sent_at: datetime


class DraftPreview(BaseModel):
    """What would be sent, without sending it."""

    subject: str
    body: str
    draft_status: str
    sendable: bool
    blocked_reason: str | None = None
