"""Credential rotation and response parsing for the OpenAI-compatible client.

Every test drives the real `_sync_complete`; only `urlopen` is replaced, so the
header construction, retry decision and payload parsing under test are the ones
that run in production.
"""

import http.client
import json
import urllib.error
from io import BytesIO

import pytest

from app.core.config import Settings
from app.services.ai.providers import OpenAICompatibleProvider


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def ok_payload(content: str = "An answer.") -> bytes:
    return json.dumps(
        {
            "id": "resp-1",
            "model": "test-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    ).encode("utf-8")


def http_error(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://example.test/chat/completions", status, "err", {}, BytesIO(b'{"error":"upstream"}')
    )


def provider(**kwargs) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        key="remote",
        base_url="https://example.test/v1",
        model_name="test-model",
        api_key="key-primary",
        **kwargs,
    )


def install(monkeypatch, behaviours):
    """Queue one behaviour per call: an exception to raise or bytes to return."""
    calls: list[str | None] = []

    def fake_urlopen(request, timeout=None):  # noqa: ARG001
        calls.append(request.headers.get("Authorization"))
        outcome = behaviours[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)

    monkeypatch.setattr("app.services.ai.providers.urllib.request.urlopen", fake_urlopen)
    return calls


# --- rotation ----------------------------------------------------------------


def test_a_rate_limited_key_falls_through_to_the_next(monkeypatch):
    calls = install(monkeypatch, [http_error(429), ok_payload()])
    result = provider(fallback_api_keys=("key-spare",))._sync_complete(
        system="s", user="u", max_output_tokens=100
    )
    assert result.content == "An answer."
    assert calls == ["Bearer key-primary", "Bearer key-spare"]
    # The caller can see which credential actually served the request.
    assert result.metadata["credential_index"] == 1


def test_an_overloaded_upstream_is_retried_on_another_key(monkeypatch):
    calls = install(monkeypatch, [http_error(503), ok_payload()])
    provider(fallback_api_keys=("key-spare",))._sync_complete(
        system="s", user="u", max_output_tokens=100
    )
    assert len(calls) == 2


def test_an_authentication_failure_is_not_retried(monkeypatch):
    # A bad key is a configuration error; trying more keys multiplies the same
    # failure and hides the cause.
    calls = install(monkeypatch, [http_error(401), ok_payload()])
    with pytest.raises(RuntimeError, match="HTTP 401"):
        provider(fallback_api_keys=("key-spare",))._sync_complete(
            system="s", user="u", max_output_tokens=100
        )
    assert len(calls) == 1


def test_exhausting_every_credential_reports_each_attempt(monkeypatch):
    install(monkeypatch, [http_error(429), http_error(429), http_error(503), http_error(429)])
    with pytest.raises(RuntimeError) as exc:
        provider(fallback_api_keys=("key-2", "key-3"))._sync_complete(
            system="s", user="u", max_output_tokens=100
        )
    message = str(exc.value)
    assert "credential 0: HTTP 429" in message
    assert "credential 2: HTTP 503" in message


def test_duplicate_spare_keys_are_not_tried_twice(monkeypatch):
    calls = install(monkeypatch, [http_error(429), ok_payload()])
    provider(fallback_api_keys=("key-primary", "key-spare"))._sync_complete(
        system="s", user="u", max_output_tokens=100
    )
    assert calls == ["Bearer key-primary", "Bearer key-spare"]


# --- parsing -----------------------------------------------------------------


def test_a_reasoning_model_that_never_emits_text_says_so(monkeypatch):
    # Gemini's reasoning models spend the output budget on hidden thinking and
    # return a message with no content field at all.
    truncated = json.dumps(
        {"choices": [{"index": 0, "finish_reason": "length", "message": {"role": "assistant"}}]}
    ).encode("utf-8")
    install(monkeypatch, [truncated])
    with pytest.raises(RuntimeError, match="output-token limit"):
        provider()._sync_complete(system="s", user="u", max_output_tokens=16)


def test_a_filtered_response_is_named_as_such(monkeypatch):
    filtered = json.dumps(
        {"choices": [{"finish_reason": "content_filter", "message": {"role": "assistant"}}]}
    ).encode("utf-8")
    install(monkeypatch, [filtered])
    with pytest.raises(RuntimeError, match="content filter"):
        provider()._sync_complete(system="s", user="u", max_output_tokens=100)


def test_an_empty_choice_list_is_reported(monkeypatch):
    install(monkeypatch, [json.dumps({"choices": []}).encode("utf-8")])
    with pytest.raises(RuntimeError, match="no choices"):
        provider()._sync_complete(system="s", user="u", max_output_tokens=100)


# --- settings ----------------------------------------------------------------


def test_fallback_keys_parse_from_a_comma_separated_setting():
    settings = Settings(
        _env_file=None,
        ai_remote_api_key_fallbacks=" key-a , key-b ,, key-c ",
    )
    assert settings.ai_remote_fallback_api_keys == ("key-a", "key-b", "key-c")


def test_no_fallback_setting_yields_no_spare_keys():
    assert Settings(_env_file=None).ai_remote_fallback_api_keys == ()


# --- connection-level failures ------------------------------------------------


def test_a_dropped_connection_is_retried(monkeypatch):
    # Gemini dropped a TLS handshake mid-request during local testing. There is
    # no HTTP status on such a failure, and it says nothing about the request.
    dropped = urllib.error.URLError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF in violation of protocol")
    calls = install(monkeypatch, [dropped, ok_payload()])
    monkeypatch.setattr("app.services.ai.providers.time.sleep", lambda _: None)
    result = provider(fallback_api_keys=("key-spare",))._sync_complete(
        system="s", user="u", max_output_tokens=100
    )
    assert result.content == "An answer."
    assert len(calls) == 2


def test_a_single_credential_still_gets_a_second_attempt(monkeypatch):
    # A transport blip is not the credential's fault, so a lone key must not
    # mean a single chance.
    dropped = urllib.error.URLError("connection reset")
    calls = install(monkeypatch, [dropped, ok_payload()])
    monkeypatch.setattr("app.services.ai.providers.time.sleep", lambda _: None)
    provider()._sync_complete(system="s", user="u", max_output_tokens=100)
    assert calls == ["Bearer key-primary", "Bearer key-primary"]


def test_a_connection_failure_reports_the_reason_not_a_status(monkeypatch):
    dropped = urllib.error.URLError("name resolution failed")
    install(monkeypatch, [dropped, dropped])
    monkeypatch.setattr("app.services.ai.providers.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="name resolution failed"):
        provider()._sync_complete(system="s", user="u", max_output_tokens=100)


def test_a_connection_dropped_while_reading_is_retried(monkeypatch):
    """The failure seen locally on the first request after a cold start.

    http.client.RemoteDisconnected is an OSError but not a URLError, so a
    handler that catches only URLError lets it escape the retry loop and the
    run fails outright.
    """
    dropped = http.client.RemoteDisconnected("Remote end closed connection without response")
    calls = install(monkeypatch, [dropped, ok_payload()])
    monkeypatch.setattr("app.services.ai.providers.time.sleep", lambda _: None)
    result = provider(fallback_api_keys=("key-spare",))._sync_complete(
        system="s", user="u", max_output_tokens=100
    )
    assert result.content == "An answer."
    assert len(calls) == 2


def test_a_socket_timeout_is_retried(monkeypatch):
    calls = install(monkeypatch, [TimeoutError("timed out"), ok_payload()])
    monkeypatch.setattr("app.services.ai.providers.time.sleep", lambda _: None)
    provider()._sync_complete(system="s", user="u", max_output_tokens=100)
    assert len(calls) == 2
