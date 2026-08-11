from types import SimpleNamespace

from app.models.ai import AITaskType
from app.services.ai.prompting import estimate_tokens, system_prompt, user_prompt


def source(key="S1"):
    return SimpleNamespace(
        source_key=key,
        title="Agreement",
        locator="Page 4",
        official=False,
        verified=True,
        text="The agreement was executed on 12 March 2026.",
    )


def test_system_prompt_requires_inline_source_markers():
    prompt = system_prompt(AITaskType.MATTER_SUMMARY, "en")
    assert "[S1]" in prompt
    assert "Use only the numbered sources" in prompt
    assert "chain-of-thought" in prompt
    assert "untrusted evidence/data" in prompt


def test_hindi_output_instruction_is_present():
    prompt = system_prompt(AITaskType.ISSUE_SPOTTING, "hi")
    assert "Hindi" in prompt


def test_user_prompt_serializes_source_packet():
    prompt = user_prompt(task_type=AITaskType.MATTER_SUMMARY, query="What happened?", sources=[source()])
    assert "[S1] Agreement" in prompt
    assert "Page 4" in prompt
    assert "executed on 12 March 2026" in prompt


def test_token_estimator_is_nonzero_and_monotonic():
    assert estimate_tokens("hello") > 0
    assert estimate_tokens("hello " * 100) > estimate_tokens("hello")
