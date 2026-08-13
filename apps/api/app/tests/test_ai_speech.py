"""Dictation: format limits, credential rotation, and refusal to guess."""

import json
import urllib.error
from io import BytesIO

import pytest

from app.core.config import Settings
from app.services.ai import speech


def configured(**overrides) -> Settings:
    base = {
        "_env_file": None,
        "ai_enabled": True,
        "ai_remote_enabled": True,
        "ai_remote_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "ai_remote_model": "gemini-3.7-flash",
        "ai_remote_api_key": "primary",
    }
    base.update(overrides)
    return Settings(**base)


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def transcript_payload(text: str = "One hundred and eighty days notice.") -> bytes:
    return json.dumps(
        {
            "candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 131, "candidatesTokenCount": 16},
        }
    ).encode("utf-8")


def http_error(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test", status, "err", {}, BytesIO(b"{}"))


def install(monkeypatch, behaviours):
    calls: list[dict] = []

    def fake_urlopen(request, timeout=None):  # noqa: ARG001
        calls.append({"url": request.full_url, "key": request.headers.get("X-goog-api-key")})
        outcome = behaviours[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)

    monkeypatch.setattr("app.services.ai.speech.urllib.request.urlopen", fake_urlopen)
    return calls


# --- the happy path ----------------------------------------------------------


def test_a_recording_becomes_text(monkeypatch):
    calls = install(monkeypatch, [transcript_payload()])
    result = speech.transcribe(b"audio-bytes", mime_type="audio/webm", settings=configured())
    assert result.text == "One hundred and eighty days notice."
    assert result.model_name == "gemini-3.7-flash"
    assert result.input_tokens == 131
    # The native endpoint, derived from the OpenAI-compatible base URL.
    assert calls[0]["url"].endswith("/models/gemini-3.7-flash:generateContent")
    assert "/openai/" not in calls[0]["url"]


def test_a_codec_suffix_on_the_mime_type_is_tolerated(monkeypatch):
    # MediaRecorder reports 'audio/webm;codecs=opus'.
    install(monkeypatch, [transcript_payload()])
    result = speech.transcribe(b"a", mime_type="audio/webm;codecs=opus", settings=configured())
    assert result.text


# --- refusals ----------------------------------------------------------------


def test_dictation_is_unavailable_when_remote_ai_is_off():
    with pytest.raises(speech.SpeechUnavailable, match="Remote AI is disabled"):
        speech.transcribe(b"a", mime_type="audio/webm", settings=configured(ai_enabled=False))


def test_no_credential_means_no_transcription():
    with pytest.raises(speech.SpeechUnavailable, match="No remote AI credential"):
        speech.transcribe(b"a", mime_type="audio/webm", settings=configured(ai_remote_api_key=None))


def test_an_unsupported_format_is_named():
    with pytest.raises(speech.SpeechUnavailable, match="Unsupported audio format"):
        speech.transcribe(b"a", mime_type="video/mp4", settings=configured())


def test_an_empty_recording_is_rejected():
    with pytest.raises(speech.SpeechUnavailable, match="empty"):
        speech.transcribe(b"", mime_type="audio/webm", settings=configured())


def test_an_oversized_recording_is_rejected_before_upload(monkeypatch):
    calls = install(monkeypatch, [transcript_payload()])
    with pytest.raises(speech.SpeechUnavailable, match="dictation limit"):
        speech.transcribe(
            b"x" * (speech.MAX_AUDIO_BYTES + 1), mime_type="audio/webm", settings=configured()
        )
    assert calls == []  # never left the machine


def test_silence_is_reported_rather_than_returned_as_empty_text(monkeypatch):
    install(monkeypatch, [json.dumps({"candidates": [{"content": {"parts": [{"text": "  "}]}}]}).encode()])
    with pytest.raises(speech.SpeechUnavailable, match="No speech was detected"):
        speech.transcribe(b"a", mime_type="audio/webm", settings=configured())


def test_a_blocked_prompt_surfaces_the_reason(monkeypatch):
    install(monkeypatch, [json.dumps({"promptFeedback": {"blockReason": "SAFETY"}}).encode()])
    with pytest.raises(speech.SpeechUnavailable, match="SAFETY"):
        speech.transcribe(b"a", mime_type="audio/webm", settings=configured())


# --- rotation ----------------------------------------------------------------


def test_a_rate_limited_credential_falls_through(monkeypatch):
    calls = install(monkeypatch, [http_error(429), transcript_payload()])
    result = speech.transcribe(
        b"a",
        mime_type="audio/webm",
        settings=configured(ai_remote_api_key_fallbacks="spare"),
    )
    assert result.metadata["credential_index"] == 1
    assert [c["key"] for c in calls] == ["primary", "spare"]


def test_an_authentication_failure_is_not_retried(monkeypatch):
    calls = install(monkeypatch, [http_error(403), transcript_payload()])
    with pytest.raises(speech.SpeechUnavailable, match="HTTP 403"):
        speech.transcribe(
            b"a", mime_type="audio/webm", settings=configured(ai_remote_api_key_fallbacks="spare")
        )
    assert len(calls) == 1


def test_a_dropped_connection_moves_to_the_next_credential(monkeypatch):
    calls = install(monkeypatch, [urllib.error.URLError("reset"), transcript_payload()])
    speech.transcribe(
        b"a", mime_type="audio/webm", settings=configured(ai_remote_api_key_fallbacks="spare")
    )
    assert len(calls) == 2
