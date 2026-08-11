from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.knowledge import (
    KnowledgeAnnotationKind, KnowledgeAssetKind, KnowledgeAssetStatus, KnowledgeCollectionStatus,
    KnowledgeLanguage, KnowledgeSourceType, MatterPlaybookStatus, ResearchCollectionStatus,
    SanitizationStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class KnowledgeCollectionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=260)
    description: str | None = None
    practice_area: str | None = Field(default=None, max_length=180)


class KnowledgeCollectionRead(ORMModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    status: KnowledgeCollectionStatus
    practice_area: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeSourceCreate(BaseModel):
    source_type: KnowledgeSourceType
    source_id: UUID | None = None
    source_matter_id: UUID | None = None
    label: str = Field(min_length=1, max_length=500)
    locator: str | None = Field(default=None, max_length=300)
    excerpt: str | None = None
    verified: bool = False
    metadata_json: dict = Field(default_factory=dict)


class KnowledgeAssetCreate(BaseModel):
    collection_id: UUID | None = None
    source_matter_id: UUID | None = None
    title: str = Field(min_length=2, max_length=450)
    kind: KnowledgeAssetKind
    language: KnowledgeLanguage = KnowledgeLanguage.ENGLISH
    body_en: str | None = None
    body_hi: str | None = None
    summary: str | None = None
    jurisdiction: str | None = Field(default="India", max_length=160)
    practice_area: str | None = Field(default=None, max_length=180)
    matter_type: str | None = Field(default=None, max_length=180)
    outcome_label: str | None = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=30)
    sources: list[KnowledgeSourceCreate] = Field(default_factory=list, max_length=40)
    metadata_json: dict = Field(default_factory=dict)


class KnowledgeAssetUpdate(BaseModel):
    collection_id: UUID | None = None
    title: str | None = Field(default=None, min_length=2, max_length=450)
    language: KnowledgeLanguage | None = None
    body_en: str | None = None
    body_hi: str | None = None
    summary: str | None = None
    jurisdiction: str | None = Field(default=None, max_length=160)
    practice_area: str | None = Field(default=None, max_length=180)
    matter_type: str | None = Field(default=None, max_length=180)
    outcome_label: str | None = Field(default=None, max_length=120)
    quality_score: float | None = Field(default=None, ge=0, le=1)
    sanitization_status: SanitizationStatus | None = None
    metadata_json: dict | None = None


class KnowledgeSourceRead(ORMModel):
    id: UUID
    asset_id: UUID
    source_type: KnowledgeSourceType
    source_id: UUID | None
    source_matter_id: UUID | None
    label: str
    locator: str | None
    excerpt: str | None
    verified: bool
    metadata_json: dict


class KnowledgeVersionRead(ORMModel):
    id: UUID
    asset_id: UUID
    version_number: int
    label: str
    title: str
    body_en: str | None
    body_hi: str | None
    summary: str | None
    content_hash: str
    created_at: datetime


class KnowledgeAssetRead(ORMModel):
    id: UUID
    organization_id: UUID
    collection_id: UUID | None
    source_matter_id: UUID | None
    title: str
    kind: KnowledgeAssetKind
    language: KnowledgeLanguage
    status: KnowledgeAssetStatus
    sanitization_status: SanitizationStatus
    body_en: str | None
    body_hi: str | None
    summary: str | None
    jurisdiction: str | None
    practice_area: str | None
    matter_type: str | None
    outcome_label: str | None
    quality_score: float
    usage_count: int
    content_hash: str
    approved_at: datetime | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class KnowledgeAssetDetail(KnowledgeAssetRead):
    sources: list[KnowledgeSourceRead] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_access_restricted: bool = False


class KnowledgeReviewRequest(BaseModel):
    sanitization_status: SanitizationStatus = SanitizationStatus.REVIEWED
    review_note: str | None = Field(default=None, max_length=2000)


class KnowledgeSearchResult(BaseModel):
    asset: KnowledgeAssetRead
    score: float
    lexical_score: float
    quality_score: float
    snippet: str
    tags: list[str] = Field(default_factory=list)


class KnowledgeSearchResponse(BaseModel):
    query: str
    normalized_query: str
    result_count: int
    results: list[KnowledgeSearchResult]


class AnnotationCreate(BaseModel):
    kind: KnowledgeAnnotationKind = KnowledgeAnnotationKind.NOTE
    body: str = Field(min_length=1, max_length=8000)
    anchor_json: dict = Field(default_factory=dict)


class AnnotationRead(ORMModel):
    id: UUID
    asset_id: UUID
    membership_id: UUID | None
    kind: KnowledgeAnnotationKind
    body: str
    anchor_json: dict
    resolved: bool
    created_at: datetime


class MatterPlaybookCreate(BaseModel):
    code: str = Field(min_length=2, max_length=160)
    name_en: str = Field(min_length=2, max_length=300)
    name_hi: str | None = Field(default=None, max_length=300)
    description: str | None = None
    practice_area: str | None = Field(default=None, max_length=180)
    matter_type: str | None = Field(default=None, max_length=180)
    version: int = Field(default=1, ge=1)


class MatterPlaybookRead(ORMModel):
    id: UUID
    organization_id: UUID
    code: str
    name_en: str
    name_hi: str | None
    description: str | None
    practice_area: str | None
    matter_type: str | None
    version: int
    status: MatterPlaybookStatus
    approved_at: datetime | None
    created_at: datetime


class MatterPlaybookItemCreate(BaseModel):
    asset_id: UUID | None = None
    step_code: str = Field(min_length=2, max_length=160)
    title_en: str = Field(min_length=2, max_length=350)
    title_hi: str | None = Field(default=None, max_length=350)
    stage: str | None = Field(default=None, max_length=160)
    position: int = Field(ge=1)
    required: bool = False
    instructions: str | None = None
    metadata_json: dict = Field(default_factory=dict)


class MatterPlaybookItemRead(ORMModel):
    id: UUID
    playbook_id: UUID
    asset_id: UUID | None
    step_code: str
    title_en: str
    title_hi: str | None
    stage: str | None
    position: int
    required: bool
    instructions: str | None
    metadata_json: dict


class ResearchCollectionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=350)
    description: str | None = None
    practice_area: str | None = Field(default=None, max_length=180)
    issue_key: str | None = Field(default=None, max_length=180)


class ResearchCollectionRead(ORMModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    practice_area: str | None
    issue_key: str | None
    status: ResearchCollectionStatus
    approved_at: datetime | None
    created_at: datetime


class ResearchCollectionItemCreate(BaseModel):
    judgment_id: UUID
    paragraph_id: UUID | None = None
    position: int = Field(ge=1)
    proposition: str | None = None
    note: str | None = None
    verified: bool = False


class ResearchCollectionItemRead(ORMModel):
    id: UUID
    collection_id: UUID
    judgment_id: UUID
    paragraph_id: UUID | None
    position: int
    proposition: str | None
    note: str | None
    verified: bool
    metadata_json: dict


class KnowledgeDashboard(BaseModel):
    approved_assets: int
    drafts_in_review: int
    collections: int
    approved_playbooks: int
    authority_collections: int
    total_reuse_count: int

class PromoteDraftSectionRequest(BaseModel):
    section_id: UUID
    collection_id: UUID | None = None
    title: str | None = Field(default=None, max_length=450)
    kind: KnowledgeAssetKind = KnowledgeAssetKind.PLEADING_SECTION
    practice_area: str | None = Field(default=None, max_length=180)
    matter_type: str | None = Field(default=None, max_length=180)
    tags: list[str] = Field(default_factory=list, max_length=30)


class PromoteContractClauseRequest(BaseModel):
    clause_id: UUID
    collection_id: UUID | None = None
    title: str | None = Field(default=None, max_length=450)
    practice_area: str | None = Field(default=None, max_length=180)
    matter_type: str | None = Field(default=None, max_length=180)
    tags: list[str] = Field(default_factory=list, max_length=30)
