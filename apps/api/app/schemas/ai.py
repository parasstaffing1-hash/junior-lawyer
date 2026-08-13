from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai import (
    ConversationMessageRole,
    ConversationStatus,
    AICitationStatus,
    AIClaimStatus,
    AIReviewStatus,
    AIRouteTier,
    AIRunStatus,
    AISourceType,
    AITaskType,
    AIVerificationStatus,
)


class AIReasoningRequest(BaseModel):
    matter_id: UUID | None = None
    task_type: AITaskType
    query: str = Field(min_length=2, max_length=8000)
    output_language: str = Field(default="en", pattern="^(en|hi|bilingual)$")
    prefer_local: bool = True
    allow_remote: bool = False
    allow_local_for_high_complexity: bool = False
    include_corpus: bool = True
    max_sources: int = Field(default=12, ge=2, le=24)
    max_input_tokens: int = Field(default=6000, ge=500, le=30000)
    max_output_tokens: int = Field(default=1200, ge=128, le=8000)


class AIRouteDecisionRead(BaseModel):
    tier: AIRouteTier
    ai_required: bool
    provider_key: str | None = None
    model_name: str | None = None
    reason: str
    quality_warning: str | None = None
    estimated_input_tokens: int = 0
    source_count: int = 0


class AISourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    ordinal: int
    source_key: str
    source_type: AISourceType
    source_record_id: str
    title: str
    locator: str | None
    text: str
    source_url: str | None
    official: bool
    verified: bool
    relevance_score: float
    metadata_json: dict


class AIClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ordinal: int
    claim_text: str
    substantive: bool
    cited_source_keys_json: list
    support_score: float
    status: AIClaimStatus
    explanation: str | None


class AICitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_citation: str
    normalized_citation: str | None
    status: AICitationStatus
    matched_judgment_id: UUID | None
    cited_source_keys_json: list
    metadata_json: dict


class AIUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_key: str
    model_name: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    latency_ms: int | None
    provider_reported_cost_microunits: int | None
    currency: str | None
    metadata_json: dict


class AIBudget(BaseModel):
    """Token budget for a prepared run.

    Deterministic tasks never build a prompt, so only the input ceiling is
    populated for those; the remaining fields keep their defaults.
    """

    max_input_tokens: int
    max_output_tokens: int = 0
    estimated_input_tokens: int = 0
    within_budget: bool = True
    retrieval: dict = Field(default_factory=dict)


class AIPrepareResponse(BaseModel):
    routing: AIRouteDecisionRead
    sources: list[AISourceRead]
    prompt_preview: str
    budget: AIBudget


class AIRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    matter_id: UUID | None
    task_type: AITaskType
    query: str
    output_language: str
    route_tier: AIRouteTier
    status: AIRunStatus
    provider_key: str | None
    model_name: str | None
    max_input_tokens: int
    max_output_tokens: int
    estimated_input_tokens: int
    actual_input_tokens: int | None
    actual_output_tokens: int | None
    routing_json: dict
    retrieval_json: dict
    response_text: str | None
    verification_status: AIVerificationStatus
    verification_summary_json: dict
    review_status: AIReviewStatus
    review_notes: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    error_message: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    sources: list[AISourceRead] = Field(default_factory=list)
    claims: list[AIClaimRead] = Field(default_factory=list)
    citations: list[AICitationRead] = Field(default_factory=list)
    usage_events: list[AIUsageRead] = Field(default_factory=list)


class AIReviewRequest(BaseModel):
    status: AIReviewStatus
    reviewed_by: str = Field(min_length=1, max_length=250)
    notes: str | None = Field(default=None, max_length=4000)


class AIProviderStatusRead(BaseModel):
    ai_enabled: bool
    local_enabled: bool
    local_model: str | None
    remote_enabled: bool
    remote_model: str | None
    remote_calls_require_explicit_opt_in: bool = True
    secrets_persisted: bool = False


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=250)
    matter_id: UUID | None = None
    jurisdiction: str = Field(default="India", max_length=120)
    output_language: str = Field(default="en", pattern="^(en|hi|bilingual)$")
    document_ids: list[UUID] = Field(default_factory=list)


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=250)


class ConversationStatusUpdate(BaseModel):
    status: ConversationStatus


class ConversationMessageCreate(BaseModel):
    question: str = Field(min_length=2, max_length=8000)
    task_type: AITaskType = AITaskType.RESEARCH_SYNTHESIS
    prefer_local: bool = True
    allow_remote: bool = False
    allow_local_for_high_complexity: bool = False
    include_corpus: bool = True
    max_sources: int = Field(default=12, ge=2, le=24)
    max_input_tokens: int = Field(default=6000, ge=500, le=30000)
    max_output_tokens: int = Field(default=1200, ge=128, le=8000)


class ConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ordinal: int
    role: ConversationMessageRole
    content: str
    run_id: UUID | None
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    matter_id: UUID | None
    jurisdiction: str
    output_language: str
    status: ConversationStatus
    document_ids_json: list[str] = Field(default_factory=list)
    message_count: int
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    conversation: ConversationRead
    messages: list[ConversationMessageRead] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    """What a posted question produces: both turns plus the run behind the
    answer, so the client never needs a second request to show citations."""

    conversation: ConversationRead
    question: ConversationMessageRead
    answer: ConversationMessageRead
    run: AIRunRead
