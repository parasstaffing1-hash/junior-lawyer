from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ExportFormat(str, Enum):
    DOCX = "docx"
    PDF = "pdf"


class ExportSourceType(str, Enum):
    LEGAL_NOTICE = "legal_notice"
    AFFIDAVIT = "affidavit"
    CASE_TIMELINE = "case_timeline"
    EVIDENCE_INDEX = "evidence_index"
    LEGAL_CHECKLIST = "legal_checklist"
    CLIENT_INTAKE = "client_intake"
    GENERIC = "generic"


class PageSize(str, Enum):
    A4 = "a4"
    LETTER = "letter"


class ExportTable(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    headers: list[str] = Field(min_length=1, max_length=20)
    rows: list[list[str]] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def validate_rows(self) -> "ExportTable":
        width = len(self.headers)
        for index, row in enumerate(self.rows, start=1):
            if len(row) != width:
                raise ValueError(
                    f"table row {index} has {len(row)} cells; expected {width}"
                )
        return self


class GenericExportSection(BaseModel):
    heading: str | None = Field(default=None, max_length=300)
    paragraphs: list[str] = Field(default_factory=list, max_length=1000)
    bullet_items: list[str] = Field(default_factory=list, max_length=1000)
    numbered_items: list[str] = Field(default_factory=list, max_length=1000)
    tables: list[ExportTable] = Field(default_factory=list, max_length=50)


class GenericExportDocument(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    subtitle: str | None = Field(default=None, max_length=500)
    metadata: dict[str, str] = Field(default_factory=dict)
    sections: list[GenericExportSection] = Field(default_factory=list, max_length=250)
    disclaimer: str | None = Field(default=None, max_length=10_000)


class ExportOptions(BaseModel):
    page_size: PageSize = PageSize.A4
    margin_mm: float = Field(default=20.0, ge=10.0, le=40.0)
    include_disclaimer: bool = True
    include_generated_footer: bool = True
    header_text: str | None = Field(default=None, max_length=200)
    footer_text: str | None = Field(default=None, max_length=200)
    filename: str | None = Field(default=None, max_length=180)


class DocumentExportRequest(BaseModel):
    source_type: ExportSourceType
    output_format: ExportFormat
    source: dict[str, Any]
    options: ExportOptions = Field(default_factory=ExportOptions)


class DocumentExportPreview(BaseModel):
    source_type: ExportSourceType
    output_format: ExportFormat
    title: str
    filename: str
    section_count: int
    table_count: int
    paragraph_count: int
    page_size: PageSize
    warnings: list[str]


class GeneratedDocument(BaseModel):
    filename: str
    media_type: str
    sha256: str
    size_bytes: int
    page_count: int | None
    warnings: list[str]
