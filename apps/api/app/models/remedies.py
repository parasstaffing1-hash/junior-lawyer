from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class RemedyPackStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class RemedyAnalysisStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    REVIEWED = "reviewed"
    SUPERSEDED = "superseded"


class RemedyCandidateStatus(StrEnum):
    POSSIBLE = "possible"
    CONDITIONAL = "conditional"
    NOT_MAINTAINABLE = "not_maintainable"
    NEEDS_RESEARCH = "needs_research"
    SELECTED = "selected"
    DISMISSED = "dismissed"


class RemedyAuthorityType(StrEnum):
    STATUTE = "statute"
    RULE = "rule"
    JUDGMENT = "judgment"
    CONSTITUTION = "constitution"
    PROCEDURE = "procedure"
    OTHER = "other"


class RemedyMemoStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"


class RemedyRulePack(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "remedy_rule_packs"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_remedy_pack_code_version"),)

    code: Mapped[str] = mapped_column(String(180), index=True)
    name_en: Mapped[str] = mapped_column(String(300))
    name_hi: Mapped[str | None] = mapped_column(String(300), nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String(120), default="India", index=True)
    proceeding_type: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    court_level: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    status: Mapped[RemedyPackStatus] = mapped_column(Enum(RemedyPackStatus, native_enum=False), default=RemedyPackStatus.DRAFT, index=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(350), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_citation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RemedyRule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "remedy_rules"
    __table_args__ = (UniqueConstraint("pack_id", "code", name="uq_remedy_rule_pack_code"),)

    pack_id: Mapped[UUID] = mapped_column(ForeignKey("remedy_rule_packs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(180), index=True)
    remedy_name_en: Mapped[str] = mapped_column(String(300))
    remedy_name_hi: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description_en: Mapped[str] = mapped_column(Text)
    description_hi: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, index=True)

    case_stage_patterns_json: Mapped[list] = mapped_column(JSON, default=list)
    status_patterns_json: Mapped[list] = mapped_column(JSON, default=list)
    court_level_patterns_json: Mapped[list] = mapped_column(JSON, default=list)
    order_type_patterns_json: Mapped[list] = mapped_column(JSON, default=list)
    act_patterns_json: Mapped[list] = mapped_column(JSON, default=list)
    section_patterns_json: Mapped[list] = mapped_column(JSON, default=list)
    requires_final_order: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_latest_order: Mapped[bool] = mapped_column(Boolean, default=False)

    forum_json: Mapped[dict] = mapped_column(JSON, default=dict)
    limitation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    maintainability_json: Mapped[dict] = mapped_column(JSON, default=dict)
    required_documents_json: Mapped[list] = mapped_column(JSON, default=list)
    procedural_steps_json: Mapped[list] = mapped_column(JSON, default=list)
    risks_json: Mapped[list] = mapped_column(JSON, default=list)
    drafting_json: Mapped[dict] = mapped_column(JSON, default=dict)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RemedyRuleAuthority(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "remedy_rule_authorities"
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("remedy_rules.id", ondelete="CASCADE"), index=True)
    authority_type: Mapped[RemedyAuthorityType] = mapped_column(Enum(RemedyAuthorityType, native_enum=False), index=True)
    statute_section_id: Mapped[UUID | None] = mapped_column(ForeignKey("statute_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    judgment_id: Mapped[UUID | None] = mapped_column(ForeignKey("judgments.id", ondelete="SET NULL"), nullable=True, index=True)
    citation: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    proposition: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class RemedyAnalysis(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "remedy_analyses"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    saved_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("saved_cases.id", ondelete="CASCADE"), nullable=True, index=True)
    created_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    language: Mapped[str] = mapped_column(String(30), default="en", index=True)
    status: Mapped[RemedyAnalysisStatus] = mapped_column(Enum(RemedyAnalysisStatus, native_enum=False), default=RemedyAnalysisStatus.REVIEW_REQUIRED, index=True)
    case_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    disclaimer: Mapped[str] = mapped_column(Text)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RemedyCandidate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "remedy_candidates"

    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("remedy_analyses.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[UUID | None] = mapped_column(ForeignKey("remedy_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    remedy_code: Mapped[str] = mapped_column(String(180), index=True)
    remedy_name_en: Mapped[str] = mapped_column(String(300))
    remedy_name_hi: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[RemedyCandidateStatus] = mapped_column(Enum(RemedyCandidateStatus, native_enum=False), default=RemedyCandidateStatus.POSSIBLE, index=True)
    applicability_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    why_applicable_json: Mapped[list] = mapped_column(JSON, default=list)
    forum_json: Mapped[dict] = mapped_column(JSON, default=dict)
    deadline_json: Mapped[dict] = mapped_column(JSON, default=dict)
    maintainability_json: Mapped[dict] = mapped_column(JSON, default=dict)
    required_documents_json: Mapped[list] = mapped_column(JSON, default=list)
    procedural_steps_json: Mapped[list] = mapped_column(JSON, default=list)
    risks_json: Mapped[list] = mapped_column(JSON, default=list)
    drafting_json: Mapped[dict] = mapped_column(JSON, default=dict)
    lawyer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RemedyCandidateAuthority(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "remedy_candidate_authorities"
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("remedy_candidates.id", ondelete="CASCADE"), index=True)
    authority_type: Mapped[RemedyAuthorityType] = mapped_column(Enum(RemedyAuthorityType, native_enum=False), index=True)
    statute_section_id: Mapped[UUID | None] = mapped_column(ForeignKey("statute_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    judgment_id: Mapped[UUID | None] = mapped_column(ForeignKey("judgments.id", ondelete="SET NULL"), nullable=True, index=True)
    citation: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    proposition: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_rank: Mapped[int] = mapped_column(Integer, default=0)


class RemedyMemo(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "remedy_memos"
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("remedy_candidates.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(30), default="en")
    status: Mapped[RemedyMemoStatus] = mapped_column(Enum(RemedyMemoStatus, native_enum=False), default=RemedyMemoStatus.REVIEW_REQUIRED, index=True)
    content: Mapped[str] = mapped_column(Text)
    source_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_deterministically: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RemedyDraftLink(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "remedy_draft_links"
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("remedy_candidates.id", ondelete="CASCADE"), index=True)
    legal_draft_id: Mapped[UUID] = mapped_column(ForeignKey("legal_drafts.id", ondelete="CASCADE"), index=True)
    requested_document_kind: Mapped[str] = mapped_column(String(180), index=True)
    created_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
