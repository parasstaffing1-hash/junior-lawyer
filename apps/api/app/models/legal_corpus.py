from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class LegalSourceKind(StrEnum):
    INDIA_CODE = "india_code"
    ECOURTS = "ecourts"
    SUPREME_COURT = "supreme_court"
    HIGH_COURT = "high_court"
    TRIBUNAL = "tribunal"
    MANUAL = "manual"
    OTHER = "other"


class AccessMode(StrEnum):
    OFFICIAL_DOWNLOAD = "official_download"
    MANUAL_IMPORT = "manual_import"
    API = "api"
    WEBPAGE = "webpage"


class CorpusLanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    MIXED = "mixed"
    OTHER = "other"


class CourtLevel(StrEnum):
    SUPREME_COURT = "supreme_court"
    HIGH_COURT = "high_court"
    APPELLATE_TRIBUNAL = "appellate_tribunal"
    TRIBUNAL = "tribunal"
    DISTRICT_COURT = "district_court"
    OTHER = "other"


class CitationResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class LegalSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_sources"

    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(250))
    kind: Mapped[LegalSourceKind] = mapped_column(
        Enum(LegalSourceKind, native_enum=False), index=True
    )
    base_url: Mapped[str | None] = mapped_column(String(1000))
    jurisdiction: Mapped[str] = mapped_column(String(120), default="India", index=True)
    official: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    access_mode: Mapped[AccessMode] = mapped_column(
        Enum(AccessMode, native_enum=False), default=AccessMode.MANUAL_IMPORT
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    statutes = relationship("Statute", back_populates="source", lazy="selectin")
    judgments = relationship("Judgment", back_populates="source", lazy="select")


class Statute(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "statutes"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_statutes_source_external"),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_sources.id", ondelete="RESTRICT"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(250), index=True)
    title_en: Mapped[str] = mapped_column(String(500), index=True)
    title_hi: Mapped[str | None] = mapped_column(String(500), index=True)
    short_title: Mapped[str | None] = mapped_column(String(300), index=True)
    act_number: Mapped[str | None] = mapped_column(String(80), index=True)
    act_year: Mapped[int | None] = mapped_column(Integer, index=True)
    enactment_date: Mapped[date | None] = mapped_column(Date, index=True)
    ministry: Mapped[str | None] = mapped_column(String(250), index=True)
    department: Mapped[str | None] = mapped_column(String(250), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(120), default="India", index=True)
    state: Mapped[str | None] = mapped_column(String(120), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(1500))
    source_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    source = relationship("LegalSource", back_populates="statutes")
    sections = relationship(
        "StatuteSection",
        back_populates="statute",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="StatuteSection.sort_order",
    )


class StatuteSection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "statute_sections"
    __table_args__ = (
        UniqueConstraint("statute_id", "section_key", name="uq_statute_sections_key"),
    )

    statute_id: Mapped[UUID] = mapped_column(
        ForeignKey("statutes.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("statute_sections.id", ondelete="CASCADE"), nullable=True, index=True
    )
    section_key: Mapped[str] = mapped_column(String(180), index=True)
    section_number: Mapped[str] = mapped_column(String(80), index=True)
    provision_type: Mapped[str] = mapped_column(String(60), default="section", index=True)
    heading_en: Mapped[str | None] = mapped_column(String(600))
    heading_hi: Mapped[str | None] = mapped_column(String(600))
    text_en: Mapped[str | None] = mapped_column(Text)
    text_hi: Mapped[str | None] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    effective_from: Mapped[date | None] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, index=True)
    version_label: Mapped[str | None] = mapped_column(String(150))
    source_url: Mapped[str | None] = mapped_column(String(1500))
    source_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    statute = relationship("Statute", back_populates="sections")
    parent = relationship("StatuteSection", remote_side="StatuteSection.id")


class Judgment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "judgments"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_judgments_source_external"),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_sources.id", ondelete="RESTRICT"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(250), index=True)
    case_title: Mapped[str] = mapped_column(String(700), index=True)
    case_number: Mapped[str | None] = mapped_column(String(250), index=True)
    neutral_citation: Mapped[str | None] = mapped_column(String(180), index=True)
    reported_citations_json: Mapped[list] = mapped_column(JSON, default=list)
    court_name: Mapped[str] = mapped_column(String(350), index=True)
    court_level: Mapped[CourtLevel] = mapped_column(
        Enum(CourtLevel, native_enum=False), default=CourtLevel.OTHER, index=True
    )
    jurisdiction: Mapped[str] = mapped_column(String(150), default="India", index=True)
    decision_date: Mapped[date | None] = mapped_column(Date, index=True)
    judges_json: Mapped[list] = mapped_column(JSON, default=list)
    bench_strength: Mapped[int | None] = mapped_column(Integer, index=True)
    acts_json: Mapped[list] = mapped_column(JSON, default=list)
    sections_json: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[CorpusLanguage] = mapped_column(
        Enum(CorpusLanguage, native_enum=False), default=CorpusLanguage.ENGLISH, index=True
    )
    full_text: Mapped[str] = mapped_column(Text, default="")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(String(1500))
    source_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    source = relationship("LegalSource", back_populates="judgments")
    paragraphs = relationship(
        "JudgmentParagraph",
        back_populates="judgment",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="JudgmentParagraph.position",
    )
    outgoing_citations = relationship(
        "JudgmentCitation",
        foreign_keys="JudgmentCitation.citing_judgment_id",
        back_populates="citing_judgment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class JudgmentParagraph(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "judgment_paragraphs"
    __table_args__ = (
        UniqueConstraint("judgment_id", "position", name="uq_judgment_paragraph_position"),
    )

    judgment_id: Mapped[UUID] = mapped_column(
        ForeignKey("judgments.id", ondelete="CASCADE"), index=True
    )
    paragraph_number: Mapped[str | None] = mapped_column(String(60), index=True)
    position: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[CorpusLanguage] = mapped_column(
        Enum(CorpusLanguage, native_enum=False), default=CorpusLanguage.ENGLISH, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    judgment = relationship("Judgment", back_populates="paragraphs")


class JudgmentCitation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "judgment_citations"
    __table_args__ = (
        UniqueConstraint(
            "citing_judgment_id", "paragraph_id", "normalized_citation",
            name="uq_judgment_citation_occurrence",
        ),
    )

    citing_judgment_id: Mapped[UUID] = mapped_column(
        ForeignKey("judgments.id", ondelete="CASCADE"), index=True
    )
    paragraph_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("judgment_paragraphs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    cited_judgment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("judgments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    raw_citation: Mapped[str] = mapped_column(String(350))
    normalized_citation: Mapped[str] = mapped_column(String(220), index=True)
    status: Mapped[CitationResolutionStatus] = mapped_column(
        Enum(CitationResolutionStatus, native_enum=False),
        default=CitationResolutionStatus.UNRESOLVED,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    citing_judgment = relationship(
        "Judgment", foreign_keys=[citing_judgment_id], back_populates="outgoing_citations"
    )
    cited_judgment = relationship("Judgment", foreign_keys=[cited_judgment_id])
    paragraph = relationship("JudgmentParagraph")
