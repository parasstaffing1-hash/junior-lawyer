from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.legal_corpus import CorpusLanguage, CourtLevel


class SearchScope(StrEnum):
    ALL = "all"
    STATUTES = "statutes"
    JUDGMENTS = "judgments"


class CorpusSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    scope: SearchScope = SearchScope.ALL
    jurisdiction: str | None = None
    court_level: CourtLevel | None = None
    court_name: str | None = None
    act: str | None = None
    section: str | None = None
    language: CorpusLanguage | None = None
    date_from: date | None = None
    date_to: date | None = None
    as_of_date: date | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SearchResultRead(BaseModel):
    id: UUID
    result_type: str
    title: str
    subtitle: str | None
    snippet: str
    score: float
    authority_score: float
    lexical_score: float
    language_score: float
    source_name: str
    source_url: str | None
    court_level: CourtLevel | None = None
    court_name: str | None = None
    decision_date: date | None = None
    act_title: str | None = None
    section_number: str | None = None
    paragraph_number: str | None = None
    metadata: dict = Field(default_factory=dict)


class CorpusSearchResponse(BaseModel):
    query: str
    normalized_query: str
    expanded_terms: list[str]
    total: int
    results: list[SearchResultRead]


class StatuteSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    statute_id: UUID
    parent_id: UUID | None
    section_key: str
    section_number: str
    provision_type: str
    heading_en: str | None
    heading_hi: str | None
    text_en: str | None
    text_hi: str | None
    effective_from: date | None
    effective_to: date | None
    version_label: str | None
    source_url: str | None
    metadata_json: dict


class StatuteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    title_en: str
    title_hi: str | None
    short_title: str | None
    act_number: str | None
    act_year: int | None
    enactment_date: date | None
    ministry: str | None
    department: str | None
    jurisdiction: str
    state: str | None
    is_active: bool
    source_url: str | None
    metadata_json: dict


class JudgmentParagraphRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    paragraph_number: str | None
    position: int
    text: str
    language: CorpusLanguage
    metadata_json: dict


class JudgmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    case_title: str
    case_number: str | None
    neutral_citation: str | None
    reported_citations_json: list
    court_name: str
    court_level: CourtLevel
    jurisdiction: str
    decision_date: date | None
    judges_json: list
    bench_strength: int | None
    acts_json: list
    sections_json: list
    language: CorpusLanguage
    source_url: str | None
    metadata_json: dict


class CitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    citing_judgment_id: UUID
    paragraph_id: UUID | None
    cited_judgment_id: UUID | None
    raw_citation: str
    normalized_citation: str
    status: str
    confidence: float
    metadata_json: dict


class CorpusStatsRead(BaseModel):
    sources: int
    statutes: int
    statute_sections: int
    judgments: int
    judgment_paragraphs: int
    citations: int
    resolved_citations: int


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    kind: str
    base_url: str | None
    jurisdiction: str
    official: bool
    access_mode: str
    enabled: bool
    notes: str | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class CitationVerifyRequest(BaseModel):
    citation: str = Field(min_length=3, max_length=350)


class CitationMatchRead(BaseModel):
    judgment_id: UUID
    case_title: str
    court_name: str
    decision_date: date | None
    neutral_citation: str | None
    reported_citations: list[str]
    source_url: str | None


class CitationVerifyResponse(BaseModel):
    raw: str
    normalized: str | None
    parsed_reporter: str | None
    status: str
    matches: list[CitationMatchRead]


class CitationGraphEdgeRead(BaseModel):
    citation_id: UUID
    citing_judgment_id: UUID
    citing_case_title: str
    citing_court_name: str
    citing_decision_date: date | None
    paragraph_id: UUID | None
    raw_citation: str
    normalized_citation: str
    source_url: str | None


class StatuteImportSection(BaseModel):
    section_number: str
    provision_type: str = "section"
    heading_en: str | None = None
    heading_hi: str | None = None
    text_en: str | None = None
    text_hi: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    version_label: str | None = None
    source_url: str | None = None
    metadata: dict = Field(default_factory=dict)


class StatuteImportRequest(BaseModel):
    source_code: str = "india_code"
    external_id: str
    title_en: str
    title_hi: str | None = None
    short_title: str | None = None
    act_number: str | None = None
    act_year: int | None = None
    enactment_date: date | None = None
    ministry: str | None = None
    department: str | None = None
    jurisdiction: str = "India"
    state: str | None = None
    source_url: str | None = None
    metadata: dict = Field(default_factory=dict)
    sections: list[StatuteImportSection] = Field(default_factory=list)


class JudgmentImportParagraph(BaseModel):
    paragraph_number: str | None = None
    text: str
    language: CorpusLanguage = CorpusLanguage.ENGLISH
    metadata: dict = Field(default_factory=dict)


class JudgmentImportRequest(BaseModel):
    source_code: str
    external_id: str
    case_title: str
    case_number: str | None = None
    neutral_citation: str | None = None
    reported_citations: list[str] = Field(default_factory=list)
    court_name: str
    court_level: CourtLevel
    jurisdiction: str = "India"
    decision_date: date | None = None
    judges: list[str] = Field(default_factory=list)
    bench_strength: int | None = None
    acts: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    language: CorpusLanguage = CorpusLanguage.ENGLISH
    source_url: str | None = None
    metadata: dict = Field(default_factory=dict)
    paragraphs: list[JudgmentImportParagraph] = Field(default_factory=list)
