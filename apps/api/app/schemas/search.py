from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.search import SearchEntityType


class SearchResult(BaseModel):
    entity_type: SearchEntityType
    entity_id: UUID
    title: str
    subtitle: str | None = None
    snippet: str = ""
    href: str
    score: float = Field(ge=0, le=1)
    badges: list[str] = Field(default_factory=list)
    matter_id: UUID | None = None
    client_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)


class SearchGroup(BaseModel):
    entity_type: SearchEntityType
    count: int
    results: list[SearchResult]


class UniversalSearchResponse(BaseModel):
    query: str
    normalized_query: str
    expanded_terms: list[str]
    result_count: int
    groups: list[SearchGroup]
    results: list[SearchResult]


class SearchPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    default_scopes_json: list
    default_language: str
    max_results: int
    include_legal_corpus: bool
    show_recent_items: bool
    command_palette_enabled: bool


class SearchPreferenceUpdate(BaseModel):
    default_scopes_json: list[str] | None = None
    default_language: str | None = None
    max_results: int | None = Field(default=None, ge=5, le=100)
    include_legal_corpus: bool | None = None
    show_recent_items: bool | None = None
    command_palette_enabled: bool | None = None


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    query: str = Field(min_length=1, max_length=1000)
    scopes: list[SearchEntityType] = Field(default_factory=list)
    filters: dict = Field(default_factory=dict)
    pinned: bool = False


class SavedSearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    query: str
    scopes_json: list
    filters_json: dict
    pinned: bool
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RecentItemCreate(BaseModel):
    entity_type: SearchEntityType
    entity_id: UUID
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=700)
    href: str = Field(min_length=1, max_length=1000)
    matter_id: UUID | None = None
    client_id: UUID | None = None


class RecentItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    entity_type: SearchEntityType
    entity_id: UUID
    title_snapshot: str
    subtitle_snapshot: str | None
    href: str
    matter_id: UUID | None
    client_id: UUID | None
    opened_at: datetime
    open_count: int


class CommandDefinition(BaseModel):
    id: str
    title: str
    description: str
    keywords: list[str]
    href: str
    shortcut: str | None = None
    write_action: bool = False

class SearchIndexJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    status: str
    entries_seen: int
    entries_created: int
    entries_updated: int
    entries_deleted: int
    duplicates_detected: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None


class SearchIndexHealth(BaseModel):
    entry_count: int
    chunk_count: int
    exact_duplicate_pairs: int
    near_duplicate_pairs: int
    by_entity: dict[str, int]
    last_completed_job_at: str | None = None
    snapshot_hash: str


class SearchDuplicateItem(BaseModel):
    id: UUID
    kind: str
    similarity: float
    hamming_distance: int
    shingle_jaccard: float
    left: dict
    right: dict
