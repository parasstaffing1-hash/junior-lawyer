from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class DocumentLanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    MIXED = "mixed"
    HINGLISH = "hinglish"
    UNKNOWN = "unknown"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ExtractionMethod(StrEnum):
    NATIVE_PDF = "native_pdf"
    OCR = "ocr"
    MIXED_PDF = "mixed_pdf"
    DOCX = "docx"
    TEXT = "text"
    IMAGE_OCR = "image_ocr"
    UNKNOWN = "unknown"


class Document(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("matter_id", "sha256", name="uq_documents_matter_sha256"),
    )

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(500))
    display_name: Mapped[str | None] = mapped_column(String(500))
    file_extension: Mapped[str | None] = mapped_column(String(20), index=True)
    mime_type: Mapped[str | None] = mapped_column(String(150))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(1000))

    page_count: Mapped[int | None] = mapped_column(Integer)
    text_char_count: Mapped[int] = mapped_column(Integer, default=0)
    detected_language: Mapped[DocumentLanguage] = mapped_column(
        Enum(DocumentLanguage, native_enum=False), default=DocumentLanguage.UNKNOWN, index=True
    )
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(ExtractionMethod, native_enum=False), default=ExtractionMethod.UNKNOWN
    )
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, native_enum=False),
        default=ProcessingStatus.PENDING,
        index=True,
    )
    processing_error: Mapped[str | None] = mapped_column(Text)

    matter = relationship("Matter", back_populates="documents")
    pages = relationship(
        "DocumentPage",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DocumentPage.page_number",
    )
    entities = relationship(
        "DocumentEntity",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
