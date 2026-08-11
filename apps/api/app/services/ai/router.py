from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.models.ai import AIRouteTier, AITaskType


DETERMINISTIC_TASKS = {
    AITaskType.EXTRACT_ENTITIES,
    AITaskType.SEARCH_CASES,
    AITaskType.LOOKUP_STATUTE,
    AITaskType.CALCULATE_DEADLINE,
    AITaskType.BUILD_CHRONOLOGY,
    AITaskType.COMPARE_DOCUMENTS,
    AITaskType.VERIFY_CITATION,
}

LOCAL_PREFERRED_TASKS = {
    AITaskType.MATTER_SUMMARY,
    AITaskType.DOCUMENT_SUMMARY,
    AITaskType.CLIENT_UPDATE,
}

HIGH_COMPLEXITY_TASKS = {
    AITaskType.RESEARCH_SYNTHESIS,
    AITaskType.ISSUE_SPOTTING,
    AITaskType.ARGUMENT_ANALYSIS,
    AITaskType.COUNTERARGUMENT,
    AITaskType.CUSTOM_DRAFTING,
    AITaskType.CUSTOM_CLAUSE,
    AITaskType.HEARING_QUESTIONS,
}


@dataclass(frozen=True, slots=True)
class RouteDecision:
    tier: AIRouteTier
    ai_required: bool
    provider_key: str | None
    model_name: str | None
    reason: str
    quality_warning: str | None = None

    def as_dict(self, *, estimated_input_tokens: int = 0, source_count: int = 0) -> dict:
        return {
            "tier": self.tier.value,
            "ai_required": self.ai_required,
            "provider_key": self.provider_key,
            "model_name": self.model_name,
            "reason": self.reason,
            "quality_warning": self.quality_warning,
            "estimated_input_tokens": estimated_input_tokens,
            "source_count": source_count,
        }


def route_task(
    task_type: AITaskType,
    *,
    settings: Settings,
    prefer_local: bool = True,
    allow_remote: bool = False,
    allow_local_for_high_complexity: bool = False,
) -> RouteDecision:
    if task_type in DETERMINISTIC_TASKS:
        return RouteDecision(
            tier=AIRouteTier.DETERMINISTIC,
            ai_required=False,
            provider_key=None,
            model_name=None,
            reason="Existing Python/rule/search services can perform this task without generative AI.",
        )

    if not settings.ai_enabled:
        return RouteDecision(
            tier=AIRouteTier.BLOCKED,
            ai_required=True,
            provider_key=None,
            model_name=None,
            reason="AI is disabled globally. Enable a local or remote provider explicitly to run this task.",
        )

    local_available = bool(settings.ai_local_enabled and settings.ai_local_base_url and settings.ai_local_model)
    remote_available = bool(
        settings.ai_remote_enabled
        and settings.ai_remote_base_url
        and settings.ai_remote_model
        and settings.ai_remote_api_key
    )

    if task_type in LOCAL_PREFERRED_TASKS:
        if local_available and prefer_local:
            return RouteDecision(
                tier=AIRouteTier.LOCAL,
                ai_required=True,
                provider_key="local",
                model_name=settings.ai_local_model,
                reason="This language task is eligible for the configured local model to avoid paid API usage.",
            )
        if remote_available and allow_remote:
            return RouteDecision(
                tier=AIRouteTier.STRONG,
                ai_required=True,
                provider_key="remote",
                model_name=settings.ai_remote_model,
                reason="Local execution is unavailable or not preferred; remote execution was explicitly allowed.",
            )
        if local_available:
            return RouteDecision(
                tier=AIRouteTier.LOCAL,
                ai_required=True,
                provider_key="local",
                model_name=settings.ai_local_model,
                reason="Remote execution is not permitted for this request; using the available local model.",
            )
        return RouteDecision(
            tier=AIRouteTier.BLOCKED,
            ai_required=True,
            provider_key=None,
            model_name=None,
            reason="No permitted model is configured for this task. Remote execution requires explicit opt-in.",
        )

    if task_type in HIGH_COMPLEXITY_TASKS:
        if remote_available and allow_remote:
            return RouteDecision(
                tier=AIRouteTier.STRONG,
                ai_required=True,
                provider_key="remote",
                model_name=settings.ai_remote_model,
                reason="High-complexity legal reasoning is routed to the configured strong provider only after explicit remote opt-in.",
            )
        if local_available and allow_local_for_high_complexity:
            return RouteDecision(
                tier=AIRouteTier.LOCAL,
                ai_required=True,
                provider_key="local",
                model_name=settings.ai_local_model,
                reason="High-complexity reasoning is using the local model because the request explicitly allowed this fallback.",
                quality_warning="Local-model quality may be insufficient for complex legal reasoning; lawyer review is mandatory.",
            )
        return RouteDecision(
            tier=AIRouteTier.BLOCKED,
            ai_required=True,
            provider_key=None,
            model_name=None,
            reason="High-complexity legal reasoning requires either explicit remote opt-in or explicit permission to use the local fallback.",
        )

    return RouteDecision(
        tier=AIRouteTier.BLOCKED,
        ai_required=True,
        provider_key=None,
        model_name=None,
        reason="No routing policy is defined for this task.",
    )
