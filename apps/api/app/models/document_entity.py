from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, Float, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class EntityType(StrEnum):
    CNR_NUMBER = "cnr_number"
    CASE_NUMBER = "case_number"
    CASE_TITLE = "case_title"
    PARTY = "party"
    COURT = "court"
    JUDGE = "judge"
    DATE = "date"
    ACT = "act"
    STATUTE_REFERENCE = "statute_reference"
    CITATION = "citation"


class DocumentEntity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_entities"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, index=True)
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, native_enum=False), index=True
    )
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[str | None] = mapped_column(Text, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    document = relationship("Document", back_populates="entities")
    page = relationship("DocumentPage", back_populates="entities")
