"""Case memory and the agent that reads it.

Two ideas live here.

`MatterMemory` is the matter's standing answer to "what do we know?". Facts,
timeline, contradictions and evidence already persist in their own tables; what
had no home was the lawyer's reading of them — the legal issues in play, the
strategy, and the questions still open. Memory holds those, plus a derived
snapshot of the rest, so an agent step can be handed one object instead of
re-querying six services.

`AgentRun` is a multi-step piece of work. Until now every AI action was one
shot: one task type, one answer. A run sequences steps, records what each one
produced, and stops at the lawyer rather than acting. Deterministic steps call
the rule engines and work with AI switched off entirely; AI steps point at the
`AIRun` that produced them, so sources, claims, citations and verification stay
where they already are rather than being copied here.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class AgentRecipe(StrEnum):
    """A named sequence of steps. Recipes are defined in code rather than as
    rows, because each one names the engines it calls; a firm-authored builder
    is a later, separate feature."""

    HEARING_PREP = "hearing_prep"


class AgentStepKind(StrEnum):
    #: Calls a rule engine. Runs whether or not a model is configured.
    DETERMINISTIC = "deterministic"
    #: Calls an AITaskType. Skipped, not failed, when AI is unavailable.
    AI = "ai"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    #: Every step finished. Nothing has been acted on — the lawyer decides.
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class AgentStepStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    #: An AI step with no provider configured, or a step whose inputs are absent.
    SKIPPED = "skipped"
    FAILED = "failed"


class MatterMemory(Base, UUIDMixin, TimestampMixin):
    """One row per matter. Upserted, never duplicated."""

    __tablename__ = "matter_memory"

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), unique=True, index=True
    )
    #: Issues in play, each {key, label, note}. Lawyer-owned; nothing writes
    #: over these automatically.
    issues_json: Mapped[list] = mapped_column(JSON, default=list)
    #: Questions the file cannot yet answer — the honest gaps.
    open_questions_json: Mapped[list] = mapped_column(JSON, default=list)
    strategy_notes: Mapped[str | None] = mapped_column(Text)
    #: Counts and keys derived from facts/timeline/contradictions/evidence at
    #: the last refresh. A cache for display and for agent inputs, never the
    #: source of truth.
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_runs"

    matter_id: Mapped[UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), index=True
    )
    recipe: Mapped[AgentRecipe] = mapped_column(Enum(AgentRecipe, native_enum=False), index=True)
    title: Mapped[str] = mapped_column(String(250))
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, native_enum=False), default=AgentRunStatus.RUNNING, index=True
    )
    output_language: Mapped[str] = mapped_column(String(20), default="en")
    #: Headline findings, assembled from the steps for the top of the report.
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    #: True when at least one AI step was skipped for want of a provider, so
    #: the report can say so rather than quietly reading as complete.
    ai_available: Mapped[bool] = mapped_column(default=False)
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(250))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps = relationship(
        "AgentStep",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AgentStep.ordinal",
    )


class AgentStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_steps"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, index=True)
    step_key: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(250))
    kind: Mapped[AgentStepKind] = mapped_column(Enum(AgentStepKind, native_enum=False), index=True)
    status: Mapped[AgentStepStatus] = mapped_column(
        Enum(AgentStepStatus, native_enum=False), default=AgentStepStatus.PENDING, index=True
    )
    #: What the step found, shaped by the step. Rendered by the UI per step_key.
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    #: Set for AI steps, so sources and verification are read from the existing
    #: AI run rather than duplicated onto the step.
    ai_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Why a step was skipped, in words a lawyer can act on.
    note: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run = relationship("AgentRun", back_populates="steps")
