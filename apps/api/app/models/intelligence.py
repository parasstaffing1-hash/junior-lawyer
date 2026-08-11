from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Date, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class FactType(StrEnum):
    DATE = "date"
    MONEY = "money"
    IDENTIFIER = "identifier"
    TEXT = "text"


class FactStatus(StrEnum):
    AUTO = "auto"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class SourceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class StatementKind(StrEnum):
    CLAIM = "claim"
    ADMISSION = "admission"
    DENIAL = "denial"


class ContradictionSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContradictionStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ReviewPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewStatus(StrEnum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    DISMISSED = "dismissed"


class ReviewItemType(StrEnum):
    FACT = "fact"
    CONTRADICTION = "contradiction"
    STATEMENT = "statement"


class MatterFact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_facts"
    __table_args__ = (
        UniqueConstraint(
            "matter_id", "fact_key", "normalized_value",
            name="uq_matter_facts_key_value",
        ),
    )

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    fact_key: Mapped[str] = mapped_column(String(220), index=True)
    fact_type: Mapped[FactType] = mapped_column(
        Enum(FactType, native_enum=False), index=True
    )
    category: Mapped[str] = mapped_column(String(100), index=True)
    label: Mapped[str] = mapped_column(String(220))
    value_text: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[str] = mapped_column(String(500), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[FactStatus] = mapped_column(
        Enum(FactStatus, native_enum=False), default=FactStatus.AUTO, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    matter = relationship("Matter", back_populates="facts")
    sources = relationship(
        "FactSource",
        back_populates="fact",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="FactSource.page_number",
    )


class FactSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "fact_sources"

    fact_id: Mapped[UUID] = mapped_column(
        ForeignKey("matter_facts.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, index=True)
    relation: Mapped[SourceRelation] = mapped_column(
        Enum(SourceRelation, native_enum=False), default=SourceRelation.SUPPORTS
    )
    quote: Mapped[str] = mapped_column(Text)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    fact = relationship("MatterFact", back_populates="sources")


class TimelineEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "timeline_events"
    __table_args__ = (
        UniqueConstraint(
            "matter_id", "event_key", name="uq_timeline_events_matter_event_key"
        ),
    )

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    event_key: Mapped[str] = mapped_column(String(500), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    event_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    matter = relationship("Matter", back_populates="timeline_events")
    sources = relationship(
        "TimelineEventSource",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TimelineEventSource.page_number",
    )


class TimelineEventSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "timeline_event_sources"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("timeline_events.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, index=True)
    quote: Mapped[str] = mapped_column(Text)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    event = relationship("TimelineEvent", back_populates="sources")


class MatterStatement(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_statements"

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, index=True)
    kind: Mapped[StatementKind] = mapped_column(
        Enum(StatementKind, native_enum=False), index=True
    )
    speaker_role: Mapped[str | None] = mapped_column(String(100), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    matter = relationship("Matter", back_populates="statements")


class MatterContradiction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_contradictions"
    __table_args__ = (
        UniqueConstraint(
            "matter_id", "contradiction_key",
            name="uq_matter_contradictions_key",
        ),
    )

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    contradiction_key: Mapped[str] = mapped_column(String(300), index=True)
    fact_key: Mapped[str] = mapped_column(String(220), index=True)
    label: Mapped[str] = mapped_column(String(250))
    explanation: Mapped[str] = mapped_column(Text)
    severity: Mapped[ContradictionSeverity] = mapped_column(
        Enum(ContradictionSeverity, native_enum=False), index=True
    )
    status: Mapped[ContradictionStatus] = mapped_column(
        Enum(ContradictionStatus, native_enum=False),
        default=ContradictionStatus.OPEN,
        index=True,
    )
    values_json: Mapped[list] = mapped_column(JSON, default=list)
    fact_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    matter = relationship("Matter", back_populates="contradictions")


class ReviewItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "review_items"

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    item_type: Mapped[ReviewItemType] = mapped_column(
        Enum(ReviewItemType, native_enum=False), index=True
    )
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(Text)
    priority: Mapped[ReviewPriority] = mapped_column(
        Enum(ReviewPriority, native_enum=False), default=ReviewPriority.MEDIUM, index=True
    )
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False), default=ReviewStatus.OPEN, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    matter = relationship("Matter", back_populates="review_items")
