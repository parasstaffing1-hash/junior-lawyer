from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class LegalDraftType(StrEnum):
    LEGAL_NOTICE = "legal_notice"
    NOTICE_REPLY = "notice_reply"
    AFFIDAVIT = "affidavit"
    APPLICATION = "application"
    PETITION = "petition"
    WRITTEN_STATEMENT = "written_statement"
    REJOINDER = "rejoinder"
    WRITTEN_SUBMISSIONS = "written_submissions"
    CHRONOLOGY = "chronology"
    ANNEXURE_INDEX = "annexure_index"
    CASE_SYNOPSIS = "case_synopsis"
    HEARING_NOTE = "hearing_note"


class LegalDraftLanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    BILINGUAL = "bilingual"


class LegalDraftStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class DraftSectionSource(StrEnum):
    DETERMINISTIC = "deterministic"
    MANUAL = "manual"
    AI = "ai"


class DraftSourceType(StrEnum):
    FACT = "fact"
    TIMELINE = "timeline"
    DOCUMENT = "document"
    STATEMENT = "statement"
    CONTRADICTION = "contradiction"
    STATUTE_SECTION = "statute_section"
    JUDGMENT_PARAGRAPH = "judgment_paragraph"
    MANUAL = "manual"


class DraftFindingLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DraftFindingStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"


class LegalDraftTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_draft_templates"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_legal_draft_templates_code_version"),
    )

    code: Mapped[str] = mapped_column(String(160), index=True)
    draft_type: Mapped[LegalDraftType] = mapped_column(
        Enum(LegalDraftType, native_enum=False), index=True
    )
    name_en: Mapped[str] = mapped_column(String(250))
    name_hi: Mapped[str | None] = mapped_column(String(250))
    description: Mapped[str | None] = mapped_column(Text)
    structure_json: Mapped[list] = mapped_column(JSON, default=list)
    questions_json: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class LegalDraft(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_drafts"

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("legal_draft_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(400), index=True)
    draft_type: Mapped[LegalDraftType] = mapped_column(
        Enum(LegalDraftType, native_enum=False), index=True
    )
    language: Mapped[LegalDraftLanguage] = mapped_column(
        Enum(LegalDraftLanguage, native_enum=False), default=LegalDraftLanguage.ENGLISH, index=True
    )
    status: Mapped[LegalDraftStatus] = mapped_column(
        Enum(LegalDraftStatus, native_enum=False), default=LegalDraftStatus.DRAFT, index=True
    )
    court_name: Mapped[str | None] = mapped_column(String(350))
    case_number: Mapped[str | None] = mapped_column(String(180), index=True)
    questionnaire_json: Mapped[dict] = mapped_column(JSON, default=dict)
    health_score: Mapped[int] = mapped_column(Integer, default=100)
    generated_filename: Mapped[str | None] = mapped_column(String(400))
    generated_storage_key: Mapped[str | None] = mapped_column(String(900))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    matter = relationship("Matter", back_populates="legal_drafts")
    template = relationship("LegalDraftTemplate")
    sections = relationship(
        "LegalDraftSection",
        back_populates="draft",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LegalDraftSection.position",
    )
    findings = relationship(
        "LegalDraftFinding",
        back_populates="draft",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LegalDraftFinding.created_at",
    )
    versions = relationship(
        "LegalDraftVersion",
        back_populates="draft",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LegalDraftVersion.version_number",
    )


class LegalDraftSection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_draft_sections"
    __table_args__ = (
        UniqueConstraint("draft_id", "position", name="uq_legal_draft_sections_position"),
    )

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_drafts.id", ondelete="CASCADE"), index=True
    )
    section_key: Mapped[str] = mapped_column(String(160), index=True)
    title_en: Mapped[str] = mapped_column(String(350))
    title_hi: Mapped[str | None] = mapped_column(String(350))
    body_en: Mapped[str] = mapped_column(Text, default="")
    body_hi: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[DraftSectionSource] = mapped_column(
        Enum(DraftSectionSource, native_enum=False), default=DraftSectionSource.DETERMINISTIC, index=True
    )
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    draft = relationship("LegalDraft", back_populates="sections")
    sources = relationship(
        "LegalDraftSource",
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LegalDraftSource.created_at",
    )


class LegalDraftSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_draft_sources"

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_drafts.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("legal_draft_sections.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_type: Mapped[DraftSourceType] = mapped_column(
        Enum(DraftSourceType, native_enum=False), index=True
    )
    source_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    label: Mapped[str] = mapped_column(String(500))
    locator: Mapped[str | None] = mapped_column(String(300))
    excerpt: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    section = relationship("LegalDraftSection", back_populates="sources")


class LegalDraftFinding(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_draft_findings"
    __table_args__ = (
        UniqueConstraint("draft_id", "rule_code", name="uq_legal_draft_findings_rule"),
    )

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_drafts.id", ondelete="CASCADE"), index=True
    )
    rule_code: Mapped[str] = mapped_column(String(180), index=True)
    section_key: Mapped[str | None] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(350))
    explanation: Mapped[str] = mapped_column(Text)
    level: Mapped[DraftFindingLevel] = mapped_column(
        Enum(DraftFindingLevel, native_enum=False), index=True
    )
    status: Mapped[DraftFindingStatus] = mapped_column(
        Enum(DraftFindingStatus, native_enum=False), default=DraftFindingStatus.OPEN, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    draft = relationship("LegalDraft", back_populates="findings")


class LegalDraftVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_draft_versions"
    __table_args__ = (
        UniqueConstraint("draft_id", "version_number", name="uq_legal_draft_versions_number"),
    )

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("legal_drafts.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String(180), default="Draft")
    sections_json: Mapped[list] = mapped_column(JSON, default=list)
    findings_json: Mapped[list] = mapped_column(JSON, default=list)
    sources_json: Mapped[list] = mapped_column(JSON, default=list)
    health_score: Mapped[int] = mapped_column(Integer, default=100)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    generated_filename: Mapped[str | None] = mapped_column(String(400))
    generated_storage_key: Mapped[str | None] = mapped_column(String(900))

    draft = relationship("LegalDraft", back_populates="versions")
