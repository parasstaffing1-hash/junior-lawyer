from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class AITaskType(StrEnum):
    EXTRACT_ENTITIES = "extract_entities"
    SEARCH_CASES = "search_cases"
    LOOKUP_STATUTE = "lookup_statute"
    CALCULATE_DEADLINE = "calculate_deadline"
    BUILD_CHRONOLOGY = "build_chronology"
    COMPARE_DOCUMENTS = "compare_documents"
    VERIFY_CITATION = "verify_citation"
    MATTER_SUMMARY = "matter_summary"
    DOCUMENT_SUMMARY = "document_summary"
    CLIENT_UPDATE = "client_update"
    RESEARCH_SYNTHESIS = "research_synthesis"
    ISSUE_SPOTTING = "issue_spotting"
    ARGUMENT_ANALYSIS = "argument_analysis"
    COUNTERARGUMENT = "counterargument"
    CUSTOM_DRAFTING = "custom_drafting"
    CUSTOM_CLAUSE = "custom_clause"
    HEARING_QUESTIONS = "hearing_questions"


class AIRouteTier(StrEnum):
    DETERMINISTIC = "deterministic"
    LOCAL = "local"
    STRONG = "strong"
    BLOCKED = "blocked"


class AIRunStatus(StrEnum):
    PREPARED = "prepared"
    RUNNING = "running"
    COMPLETED = "completed"
    VERIFICATION_FAILED = "verification_failed"
    BLOCKED = "blocked"
    FAILED = "failed"


class AIVerificationStatus(StrEnum):
    NOT_RUN = "not_run"
    PASSED = "passed"
    WARNINGS = "warnings"
    FAILED = "failed"


class AIReviewStatus(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


class AISourceType(StrEnum):
    MATTER_FACT = "matter_fact"
    TIMELINE_EVENT = "timeline_event"
    STATEMENT = "statement"
    CONTRADICTION = "contradiction"
    DOCUMENT_PAGE = "document_page"
    STATUTE_SECTION = "statute_section"
    JUDGMENT_PARAGRAPH = "judgment_paragraph"


class AIClaimStatus(StrEnum):
    SUPPORTED = "supported"
    WEAK_SUPPORT = "weak_support"
    UNCITED = "uncited"
    INVALID_SOURCE = "invalid_source"
    NON_SUBSTANTIVE = "non_substantive"


class AICitationStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    UNPARSED = "unparsed"


class AIRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_runs"

    matter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True
    )
    task_type: Mapped[AITaskType] = mapped_column(Enum(AITaskType, native_enum=False), index=True)
    query: Mapped[str] = mapped_column(Text)
    output_language: Mapped[str] = mapped_column(String(20), default="en", index=True)
    route_tier: Mapped[AIRouteTier] = mapped_column(Enum(AIRouteTier, native_enum=False), index=True)
    status: Mapped[AIRunStatus] = mapped_column(
        Enum(AIRunStatus, native_enum=False), default=AIRunStatus.PREPARED, index=True
    )
    provider_key: Mapped[str | None] = mapped_column(String(80), index=True)
    model_name: Mapped[str | None] = mapped_column(String(200), index=True)
    max_input_tokens: Mapped[int] = mapped_column(Integer, default=6000)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=1200)
    estimated_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer)
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer)
    routing_json: Mapped[dict] = mapped_column(JSON, default=dict)
    retrieval_json: Mapped[dict] = mapped_column(JSON, default=dict)
    request_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    response_text: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[AIVerificationStatus] = mapped_column(
        Enum(AIVerificationStatus, native_enum=False), default=AIVerificationStatus.NOT_RUN, index=True
    )
    verification_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    review_status: Mapped[AIReviewStatus] = mapped_column(
        Enum(AIReviewStatus, native_enum=False), default=AIReviewStatus.PENDING, index=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(250))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sources = relationship("AIRunSource", back_populates="run", cascade="all, delete-orphan", lazy="selectin", order_by="AIRunSource.ordinal")
    claims = relationship("AIRunClaim", back_populates="run", cascade="all, delete-orphan", lazy="selectin", order_by="AIRunClaim.ordinal")
    citations = relationship("AIRunCitation", back_populates="run", cascade="all, delete-orphan", lazy="selectin")
    usage_events = relationship("AIUsageEvent", back_populates="run", cascade="all, delete-orphan", lazy="selectin")


class AIRunSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_run_sources"
    __table_args__ = (UniqueConstraint("run_id", "source_key", name="uq_ai_run_source_key"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, index=True)
    source_key: Mapped[str] = mapped_column(String(20), index=True)
    source_type: Mapped[AISourceType] = mapped_column(Enum(AISourceType, native_enum=False), index=True)
    source_record_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(700))
    locator: Mapped[str | None] = mapped_column(String(400))
    text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1500))
    official: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    run = relationship("AIRun", back_populates="sources")


class AIRunClaim(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_run_claims"
    __table_args__ = (UniqueConstraint("run_id", "ordinal", name="uq_ai_run_claim_ordinal"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    substantive: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    cited_source_keys_json: Mapped[list] = mapped_column(JSON, default=list)
    support_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[AIClaimStatus] = mapped_column(Enum(AIClaimStatus, native_enum=False), index=True)
    explanation: Mapped[str | None] = mapped_column(Text)

    run = relationship("AIRun", back_populates="claims")


class AIRunCitation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_run_citations"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True)
    raw_citation: Mapped[str] = mapped_column(String(350))
    normalized_citation: Mapped[str | None] = mapped_column(String(220), index=True)
    status: Mapped[AICitationStatus] = mapped_column(Enum(AICitationStatus, native_enum=False), index=True)
    matched_judgment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("judgments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cited_source_keys_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    run = relationship("AIRun", back_populates="citations")


class AIUsageEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_usage_events"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True)
    provider_key: Mapped[str] = mapped_column(String(80), index=True)
    model_name: Mapped[str] = mapped_column(String(200), index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    provider_reported_cost_microunits: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(12))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    run = relationship("AIRun", back_populates="usage_events")
