"""Speech-to-text over Gemini's native API.

The OpenAI-compatible surface this project's provider client speaks has no
audio endpoints — /audio/transcriptions returns 404 — so dictation cannot reuse
`OpenAICompatibleProvider`. This is the smallest client that does the job, and
it deliberately reuses the same credentials, rotation policy and timeout as the
text path so there is one place to reason about remote AI.

Dictation is a remote model call. It is gated by the same explicit permission
as any other remote call, and the caller audits it.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from app.core.config import Settings

# Formats a browser MediaRecorder can produce that Gemini accepts.
SUPPORTED_MIME_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/mpeg",
    "audio/aac",
    "audio/flac",
}

# A dictated question is short. This bounds both the upload and the bill.
MAX_AUDIO_BYTES = 12 * 1024 * 1024

_INSTRUCTION = (
    "Transcribe this audio verbatim. It is a lawyer dictating a question or a "
    "note, in English, Hindi, or a mix of both. Preserve the language actually "
    "spoken — write Hindi in Devanagari and do not translate it. Keep legal "
    "citations, section numbers, dates and amounts exactly as spoken. Return "
    "only the transcript, with no preamble, commentary or quotation marks."
)


class SpeechUnavailable(RuntimeError):
    """Transcription is not configured or the upstream refused every attempt."""


@dataclass(frozen=True)
class Transcript:
    text: str
    model_name: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    metadata: dict = field(default_factory=dict)


def _endpoint(settings: Settings, model: str) -> str:
    # The native API lives beside the OpenAI-compatible one; deriving the host
    # from the configured base URL keeps a single setting to change.
    base = (settings.ai_remote_base_url or "").rstrip("/")
    root = base[: -len("/openai")] if base.endswith("/openai") else base
    return f"{root}/models/{model}:generateContent"


def _credentials(settings: Settings) -> tuple[str, ...]:
    keys = [settings.ai_remote_api_key] if settings.ai_remote_api_key else []
    for extra in settings.ai_remote_fallback_api_keys:
        if extra and extra not in keys:
            keys.append(extra)
    return tuple(keys)


def transcribe(
    audio: bytes,
    *,
    mime_type: str,
    settings: Settings,
    model: str | None = None,
) -> Transcript:
    """Return the spoken text. Raises SpeechUnavailable rather than guessing."""
    if not settings.ai_enabled or not settings.ai_remote_enabled:
        raise SpeechUnavailable("Remote AI is disabled, so dictation is unavailable")
    credentials = _credentials(settings)
    if not credentials:
        raise SpeechUnavailable("No remote AI credential is configured")
    if not audio:
        raise SpeechUnavailable("The recording was empty")
    if len(audio) > MAX_AUDIO_BYTES:
        raise SpeechUnavailable(
            f"Recording is larger than the {MAX_AUDIO_BYTES // (1024 * 1024)}MB dictation limit"
        )
    base_type = (mime_type or "").split(";", 1)[0].strip().lower()
    if base_type not in SUPPORTED_MIME_TYPES:
        raise SpeechUnavailable(f"Unsupported audio format: {mime_type!r}")

    chosen = model or settings.ai_remote_model
    if not chosen:
        raise SpeechUnavailable("No remote AI model is configured")

    body = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {"text": _INSTRUCTION},
                        {
                            "inlineData": {
                                "mimeType": base_type,
                                "data": base64.b64encode(audio).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            # Dictation is transcription, not composition.
            "generationConfig": {"temperature": 0.0},
        }
    ).encode("utf-8")

    attempts: list[str] = []
    for index, credential in enumerate(credentials):
        request = urllib.request.Request(
            _endpoint(settings, chosen),
            data=body,
            headers={"x-goog-api-key": credential, "Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=settings.ai_request_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            if exc.code in {408, 429, 500, 502, 503, 504}:
                attempts.append(f"credential {index}: HTTP {exc.code}")
                continue
            raise SpeechUnavailable(f"Transcription failed: HTTP {exc.code}") from exc
        except OSError as exc:
            # Same reasoning as the text provider: a dropped connection says
            # nothing about the request.
            attempts.append(f"credential {index}: {getattr(exc, 'reason', None) or exc}")
            continue

        latency_ms = int((time.perf_counter() - started) * 1000)
        candidates = payload.get("candidates") or []
        if not candidates:
            feedback = (payload.get("promptFeedback") or {}).get("blockReason")
            raise SpeechUnavailable(
                f"The model returned no transcript ({feedback})" if feedback
                else "The model returned no transcript"
            )
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise SpeechUnavailable("No speech was detected in the recording")
        usage = payload.get("usageMetadata") or {}
        return Transcript(
            text=text,
            model_name=chosen,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            latency_ms=latency_ms,
            metadata={"credential_index": index},
        )

    raise SpeechUnavailable("Every configured credential failed — " + "; ".join(attempts))
