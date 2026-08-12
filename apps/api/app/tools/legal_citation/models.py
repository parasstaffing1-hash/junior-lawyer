from enum import Enum

from pydantic import BaseModel, Field, model_validator


class CitationKind(str, Enum):
    SCC = "scc"
    AIR = "air"
    SCC_ONLINE = "scc_online"
    INDIA_NEUTRAL = "india_neutral"
    UK_NEUTRAL = "uk_neutral"


class CitationFormatRequest(BaseModel):
    kind: CitationKind
    year: int = Field(ge=1800, le=2200)
    volume: int | None = Field(default=None, ge=1, le=999)
    page_or_number: int = Field(ge=1, le=99_999_999)
    court_code: str | None = Field(default=None, min_length=2, max_length=24)
    division: str | None = Field(default=None, max_length=16)
    case_name: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_kind_fields(self) -> "CitationFormatRequest":
        if self.kind == CitationKind.SCC and self.volume is None:
            raise ValueError("volume is required for SCC citations")
        if self.kind in {
            CitationKind.AIR,
            CitationKind.SCC_ONLINE,
            CitationKind.INDIA_NEUTRAL,
            CitationKind.UK_NEUTRAL,
        } and not self.court_code:
            raise ValueError("court_code is required for this citation kind")
        if self.kind == CitationKind.UK_NEUTRAL and self.court_code and self.court_code.upper() == "EWCA":
            if not self.division:
                raise ValueError("division is required when court_code is EWCA")
        return self


class CitationFormatResponse(BaseModel):
    kind: CitationKind
    citation: str
    citation_with_case_name: str
    normalized_fields: dict[str, str | int | None]
    warnings: list[str]
    disclaimer: str


class CitationExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1_000_000)
    kinds: list[CitationKind] | None = Field(default=None, max_length=10)
    deduplicate: bool = True


class CitationMatch(BaseModel):
    kind: CitationKind
    raw: str
    normalized: str
    start: int
    end: int
    line: int
    column: int
    fields: dict[str, str | int | None]


class CitationExtractResponse(BaseModel):
    matches: list[CitationMatch]
    match_count: int
    unique_count: int
    kinds_found: dict[str, int]
    warnings: list[str]
    disclaimer: str
