from app.core.config import Settings
from app.models.ai import AIRouteTier, AITaskType
from app.services.ai.router import route_task


def cfg(**kwargs):
    base = {"_env_file": None, "ai_enabled": False, "ai_local_enabled": False, "ai_remote_enabled": False}
    base.update(kwargs)
    return Settings(**base)


def test_deterministic_task_never_calls_model_even_when_ai_disabled():
    decision = route_task(AITaskType.SEARCH_CASES, settings=cfg())
    assert decision.tier == AIRouteTier.DETERMINISTIC
    assert decision.ai_required is False
    assert decision.provider_key is None


def test_summary_prefers_local_model():
    decision = route_task(
        AITaskType.MATTER_SUMMARY,
        settings=cfg(ai_enabled=True, ai_local_enabled=True, ai_local_model="small-local"),
    )
    assert decision.tier == AIRouteTier.LOCAL
    assert decision.provider_key == "local"
    assert decision.model_name == "small-local"


def test_remote_requires_explicit_opt_in():
    decision = route_task(
        AITaskType.MATTER_SUMMARY,
        settings=cfg(
            ai_enabled=True,
            ai_remote_enabled=True,
            ai_remote_base_url="https://example.invalid/v1",
            ai_remote_api_key="secret",
            ai_remote_model="strong",
        ),
        allow_remote=False,
    )
    assert decision.tier == AIRouteTier.BLOCKED


def test_high_complexity_routes_remote_only_after_opt_in():
    decision = route_task(
        AITaskType.ARGUMENT_ANALYSIS,
        settings=cfg(
            ai_enabled=True,
            ai_remote_enabled=True,
            ai_remote_base_url="https://example.invalid/v1",
            ai_remote_api_key="secret",
            ai_remote_model="strong",
        ),
        allow_remote=True,
    )
    assert decision.tier == AIRouteTier.STRONG
    assert decision.provider_key == "remote"


def test_high_complexity_local_fallback_is_explicit_and_warned():
    decision = route_task(
        AITaskType.ISSUE_SPOTTING,
        settings=cfg(ai_enabled=True, ai_local_enabled=True, ai_local_model="local"),
        allow_local_for_high_complexity=True,
    )
    assert decision.tier == AIRouteTier.LOCAL
    assert decision.quality_warning


def test_high_complexity_is_blocked_without_permission():
    decision = route_task(
        AITaskType.ISSUE_SPOTTING,
        settings=cfg(ai_enabled=True, ai_local_enabled=True, ai_local_model="local"),
    )
    assert decision.tier == AIRouteTier.BLOCKED
