from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ClauseType(str, Enum):
    CONFIDENTIALITY = "confidentiality"
    TERMINATION = "termination"
    INDEMNITY = "indemnity"
    LIMITATION_OF_LIABILITY = "limitation_of_liability"
    GOVERNING_LAW = "governing_law"
    DISPUTE_RESOLUTION = "dispute_resolution"
    PAYMENT = "payment"
    TERM_RENEWAL = "term_renewal"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    DATA_PROTECTION = "data_protection"
    FORCE_MAJEURE = "force_majeure"
    NON_COMPETE = "non_compete"
    ASSIGNMENT = "assignment"
    NOTICES = "notices"
    WARRANTIES = "warranties"
    REPRESENTATIONS = "representations"
    INSURANCE = "insurance"
    AUDIT = "audit"
    COMPLIANCE = "compliance"


class MatchBasis(str, Enum):
    HEADING = "heading"
    BODY = "body"
    HEADING_AND_BODY = "heading_and_body"


class ClauseExtractionOptions(BaseModel):
    clause_types: list[ClauseType] | None = None
    minimum_confidence: float = Field(default=0.60, ge=0.0, le=1.0)
    use_body_fallback: bool = True
    include_heading_in_text: bool = True
    max_results: int = Field(default=500, ge=1, le=2_000)
    deduplicate: bool = True

    @model_validator(mode="after")
    def normalize_types(self) -> "ClauseExtractionOptions":
        if self.clause_types:
            self.clause_types = list(dict.fromkeys(self.clause_types))
        return self


class ClauseExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)
    options: ClauseExtractionOptions = Field(default_factory=ClauseExtractionOptions)


class ClauseSignal(BaseModel):
    kind: str
    value: str


class ExtractedClause(BaseModel):
    clause_type: ClauseType
    confidence: float = Field(ge=0.0, le=1.0)
    match_basis: MatchBasis
    heading: str | None = None
    normalized_heading: str | None = None
    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    signals: list[ClauseSignal] = Field(default_factory=list)


class ClauseExtractSummary(BaseModel):
    sections_detected: int
    clauses_returned: int
    clause_type_counts: dict[str, int]
    heading_based: int
    body_based: int
    heading_and_body: int


class SupportedClauseType(BaseModel):
    clause_type: ClauseType
    heading_terms: list[str]
    body_pattern_count: int


class ClauseTypesResponse(BaseModel):
    clause_types: list[SupportedClauseType]
    disclaimer: str


class ClauseExtractResponse(BaseModel):
    matches: list[ExtractedClause]
    summary: ClauseExtractSummary
    warnings: list[str]
    disclaimer: str
