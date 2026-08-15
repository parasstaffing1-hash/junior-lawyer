from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent import (
    AgentRecipe,
    AgentRunStatus,
    AgentStepKind,
    AgentStepStatus,
)


class MatterMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    matter_id: UUID
    issues_json: list[Any] = Field(default_factory=list)
    open_questions_json: list[Any] = Field(default_factory=list)
    strategy_notes: str | None = None
    snapshot_json: dict[str, Any] = Field(default_factory=dict)
    refreshed_at: datetime | None = None
    updated_at: datetime


class MatterMemoryUpdate(BaseModel):
    """Every field optional: editing the strategy must not blank the issues."""

    issues: list[Any] | None = None
    open_questions: list[Any] | None = None
    strategy_notes: str | None = None


class AgentRecipeRead(BaseModel):
    recipe: AgentRecipe
    title: str
    description: str
    step_count: int
    deterministic_step_count: int


class AgentStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ordinal: int
    step_key: str
    label: str
    kind: AgentStepKind
    status: AgentStepStatus
    output_json: dict[str, Any] = Field(default_factory=dict)
    ai_run_id: UUID | None = None
    note: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    matter_id: UUID
    recipe: AgentRecipe
    title: str
    status: AgentRunStatus
    output_language: str
    summary_json: dict[str, Any] = Field(default_factory=dict)
    ai_available: bool
    review_notes: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    error_message: str | None = None
    completed_at: datetime | None = None
    created_at: datetime


class AgentRunDetail(AgentRunRead):
    steps: list[AgentStepRead] = Field(default_factory=list)


class AgentRunCreate(BaseModel):
    matter_id: UUID
    recipe: AgentRecipe = AgentRecipe.HEARING_PREP
    output_language: str = Field(default="en", pattern="^(en|hi|bilingual)$")


class AgentRunReview(BaseModel):
    """The reviewer is taken from the session, not from here."""

    approved: bool
    notes: str | None = None
