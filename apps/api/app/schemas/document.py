from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import (
    DocumentLanguage,
    ExtractionMethod,
    ProcessingStatus,
)
from app.models.document_entity import EntityType


class DocumentRead(BaseModel):
    id: UUID
    matter_id: UUID
    filename: str
    display_name: str | None
    file_extension: str | None
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    page_count: int | None
    text_char_count: int
    detected_language: DocumentLanguage
    extraction_method: ExtractionMethod
    is_scanned: bool
    ocr_used: bool
    extracted_at: datetime | None
    processing_status: ProcessingStatus
    processing_error: str | None
    entity_counts: dict[str, int] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentPageRead(BaseModel):
    id: UUID
    document_id: UUID
    page_number: int
    text: str
    text_sha256: str | None
    char_count: int
    detected_language: DocumentLanguage
    extraction_method: ExtractionMethod
    is_scanned: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentEntityRead(BaseModel):
    id: UUID
    document_id: UUID
    page_id: UUID | None
    page_number: int | None
    entity_type: EntityType
    raw_text: str
    normalized_value: str | None
    confidence: float
    start_char: int | None
    end_char: int | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentTextRead(BaseModel):
    document_id: UUID
    filename: str
    page_count: int
    text: str


class DocumentSuggestionRead(BaseModel):
    cnr_numbers: list[str] = Field(default_factory=list)
    case_numbers: list[str] = Field(default_factory=list)
    case_titles: list[str] = Field(default_factory=list)
    courts: list[str] = Field(default_factory=list)
    judges: list[str] = Field(default_factory=list)
    acts: list[str] = Field(default_factory=list)
    statute_references: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class DocumentPageWindowRead(BaseModel):
    document_id: UUID
    filename: str
    total_pages: int
    start_page: int
    end_page: int
    has_previous: bool
    has_next: bool
    pages: list[DocumentPageRead]


class DocumentPageMatchRead(BaseModel):
    page_number: int
    snippet: str
    match_count: int
