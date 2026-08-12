from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"


class HeadingMethod(str, Enum):
    DOCX_STYLE = "docx_style"
    PDF_FONT_HEURISTIC = "pdf_font_heuristic"


class ParseOptions(BaseModel):
    include_text: bool = True
    include_pages: bool = True
    include_blocks: bool = True
    include_tables: bool = True
    detect_headings: bool = True
    max_extracted_chars: int = Field(default=5_000_000, ge=10_000, le=10_000_000)


class DocumentMetadata(BaseModel):
    original_filename: str | None
    detected_format: DocumentFormat
    mime_type: str
    file_size_bytes: int
    sha256: str
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    page_count: int | None = None
    paragraph_count: int
    table_count: int
    heading_count: int
    word_count: int
    character_count: int


class ParsedPage(BaseModel):
    page_number: int
    text: str
    char_start: int
    char_end: int


class ParsedBlock(BaseModel):
    block_index: int
    block_type: BlockType
    text: str
    char_start: int
    char_end: int
    page_number: int | None = None
    paragraph_index: int | None = None
    table_index: int | None = None
    heading_level: int | None = None


class ParsedHeading(BaseModel):
    text: str
    level: int | None
    method: HeadingMethod
    block_index: int
    char_start: int
    char_end: int
    page_number: int | None = None


class ParsedTable(BaseModel):
    table_index: int
    rows: list[list[str]]
    row_count: int
    column_count: int
    char_start: int
    char_end: int


class ParseResponse(BaseModel):
    metadata: DocumentMetadata
    text: str | None
    pages: list[ParsedPage]
    blocks: list[ParsedBlock]
    headings: list[ParsedHeading]
    tables: list[ParsedTable]
    warnings: list[str]
    disclaimer: str
