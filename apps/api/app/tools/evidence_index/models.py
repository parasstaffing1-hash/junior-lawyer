from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class IndexType(str, Enum):
    EVIDENCE = "evidence"
    EXHIBIT = "exhibit"
    ANNEXURE = "annexure"
    BUNDLE = "bundle"


class NumberingStyle(str, Enum):
    NUMERIC = "numeric"
    ALPHABETIC = "alphabetic"


class PaginationMode(str, Enum):
    NONE = "none"
    AUTO = "auto"
    PROVIDED = "provided"


class IndexDocument(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    document_date: date | None = None
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=160)
    label: str | None = Field(default=None, max_length=100)
    source_file: str | None = Field(default=None, max_length=500)
    page_count: int | None = Field(default=None, ge=1, le=100000)
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=2000)
    confidential: bool = False

    @model_validator(mode="after")
    def validate_page_pair(self) -> "IndexDocument":
        if (self.start_page is None) != (self.end_page is None):
            raise ValueError("start_page and end_page must be supplied together")
        if self.start_page is not None and self.end_page is not None:
            if self.end_page < self.start_page:
                raise ValueError("end_page cannot be earlier than start_page")
            calculated = self.end_page - self.start_page + 1
            if self.page_count is not None and self.page_count != calculated:
                raise ValueError("page_count does not match start_page/end_page")
        return self


class EvidenceIndexRequest(BaseModel):
    case_reference: str | None = Field(default=None, max_length=200)
    title: str = Field(default="Evidence / Exhibit Index", min_length=1, max_length=300)
    index_type: IndexType = IndexType.EVIDENCE
    documents: list[IndexDocument] = Field(min_length=1, max_length=5000)
    numbering_style: NumberingStyle = NumberingStyle.NUMERIC
    label_prefix: str | None = Field(default=None, max_length=40)
    numbering_start: int = Field(default=1, ge=1, le=1000000)
    zero_pad: int = Field(default=0, ge=0, le=8)
    pagination_mode: PaginationMode = PaginationMode.AUTO
    first_page: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_pagination_inputs(self) -> "EvidenceIndexRequest":
        if self.pagination_mode == PaginationMode.AUTO:
            missing = [i + 1 for i, doc in enumerate(self.documents) if doc.page_count is None]
            if missing:
                joined = ", ".join(str(i) for i in missing[:10])
                suffix = "..." if len(missing) > 10 else ""
                raise ValueError(
                    f"page_count is required for every document in auto pagination mode; missing at entries {joined}{suffix}"
                )
            if any(doc.start_page is not None for doc in self.documents):
                raise ValueError("start_page/end_page cannot be supplied in auto pagination mode")
        elif self.pagination_mode == PaginationMode.PROVIDED:
            missing = [i + 1 for i, doc in enumerate(self.documents) if doc.start_page is None]
            if missing:
                joined = ", ".join(str(i) for i in missing[:10])
                suffix = "..." if len(missing) > 10 else ""
                raise ValueError(
                    f"start_page and end_page are required for every document in provided pagination mode; missing at entries {joined}{suffix}"
                )
        return self


class RenderedIndexDocument(BaseModel):
    sequence: int
    label: str
    title: str
    document_date: date | None
    description: str | None
    category: str | None
    source_file: str | None
    page_count: int | None
    start_page: int | None
    end_page: int | None
    page_range: str | None
    notes: str | None
    confidential: bool


class EvidenceIndexSummary(BaseModel):
    document_count: int
    confidential_count: int
    dated_document_count: int
    total_pages: int | None
    first_page: int | None
    last_page: int | None
    page_gaps: list[str]
    category_counts: dict[str, int]


class EvidenceIndexResponse(BaseModel):
    case_reference: str | None
    title: str
    index_type: IndexType
    documents: list[RenderedIndexDocument]
    summary: EvidenceIndexSummary
    markdown: str
    csv: str
    warnings: list[str]
    disclaimer: str
