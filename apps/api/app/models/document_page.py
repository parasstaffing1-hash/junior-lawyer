from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.document import DocumentLanguage, ExtractionMethod


class DocumentPage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    text_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    detected_language: Mapped[DocumentLanguage] = mapped_column(
        Enum(DocumentLanguage, native_enum=False), default=DocumentLanguage.UNKNOWN
    )
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(ExtractionMethod, native_enum=False), default=ExtractionMethod.UNKNOWN
    )
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)

    document = relationship("Document", back_populates="pages")
    entities = relationship(
        "DocumentEntity",
        back_populates="page",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
