from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import Settings


class _TransientProviderError(RuntimeError):
    """An upstream failure worth retrying.

    `status` is None for connection-level failures, which carry no HTTP status.
    """

    def __init__(self, status: int | None, detail: str) -> None:
        self.label = f"HTTP {status}" if status is not None else detail
        super().__init__(f"Provider {self.label}")
        self.status = status
        self.detail = detail


@dataclass(slots=True)
class ProviderResponse:
    content: str
    model_name: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    provider_reported_cost_microunits: int | None = None
    currency: str | None = None
    metadata: dict = field(default_factory=dict)


class AIProvider(Protocol):
    key: str
    model_name: str

    async def complete(self, *, system: str, user: str, max_output_tokens: int) -> ProviderResponse: ...


class OpenAICompatibleProvider:
    """Small dependency-free client for local/remote OpenAI-compatible chat endpoints."""

    def __init__(
        self,
        *,
        key: str,
        base_url: str,
        model_name: str,
        api_key: str | None,
        timeout_seconds: int = 90,
        fallback_api_keys: tuple[str, ...] = (),
    ) -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        # Additional credentials, tried in order when the first is rate-limited
        # or the upstream is briefly overloaded. Free tiers meter per key, so a
        # second key is the difference between a stalled workspace and a slow
        # one.
        self.fallback_api_keys = tuple(fallback_api_keys)

    @property
    def _credentials(self) -> tuple[str | None, ...]:
        seen: list[str | None] = [self.api_key]
        for candidate in self.fallback_api_keys:
            if candidate and candidate not in seen:
                seen.append(candidate)
        return tuple(seen)

    # Statuses worth retrying on a different credential: quota exhaustion and a
    # briefly overloaded upstream. A 401/403/404 is a configuration error and
    # retrying it with another key only multiplies the same failure.
    RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

    # A dropped TLS connection is not the credential's fault, so one credential
    # alone still deserves a second attempt. Cycling through the credentials
    # covers quota exhaustion; the extra pass covers a transport blip.
    MAX_ATTEMPTS = 5
    RETRY_BACKOFF_SECONDS = 0.5

    def _sync_complete(self, *, system: str, user: str, max_output_tokens: int) -> ProviderResponse:
        credentials = self._credentials
        budget = min(len(credentials) + 1, self.MAX_ATTEMPTS)
        attempts: list[str] = []
        for attempt in range(budget):
            index = attempt % len(credentials)
            try:
                return self._call_once(
                    system=system,
                    user=user,
                    max_output_tokens=max_output_tokens,
                    api_key=credentials[index],
                    credential_index=index,
                )
            except _TransientProviderError as exc:
                attempts.append(f"credential {index}: {exc.label}")
                if attempt + 1 < budget:
                    time.sleep(self.RETRY_BACKOFF_SECONDS * (attempt + 1))
        raise RuntimeError(
            "Every attempt failed with a retryable error — " + "; ".join(attempts)
        )

    def _call_once(
        self,
        *,
        system: str,
        user: str,
        max_output_tokens: int,
        api_key: str | None,
        credential_index: int,
    ) -> ProviderResponse:
        body = json.dumps(
            {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.1,
                "max_tokens": max_output_tokens,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, headers=headers, method="POST"
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            if exc.code in self.RETRYABLE_STATUSES:
                raise _TransientProviderError(exc.code, detail) from exc
            raise RuntimeError(f"Provider HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            # No HTTP status at all. URLError covers DNS and TLS failures, but a
            # connection dropped while reading the response surfaces as
            # http.client.RemoteDisconnected, which is an OSError and not a
            # URLError — catching only the latter let it escape the retry loop
            # entirely. Both are transient: a dropped connection says nothing
            # about the request. HTTPError is handled above and is also an
            # OSError subclass, so its clause must stay first.
            reason = getattr(exc, "reason", None) or exc
            raise _TransientProviderError(None, f"connection failed: {reason}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("Provider returned no choices in the chat-completion payload")
        choice = choices[0] or {}
        message = choice.get("message") or {}
        content = message.get("content")
        finish_reason = choice.get("finish_reason")
        if not content:
            # Reasoning models spend the output budget on hidden thinking tokens
            # before emitting anything visible, so a truncated answer arrives as
            # a message with no content at all. Say that plainly instead of
            # calling a well-formed response unsupported.
            if finish_reason == "length":
                raise RuntimeError(
                    "Provider stopped at the output-token limit before returning any text. "
                    "Raise max_output_tokens, or choose a model that does not spend the "
                    "budget on hidden reasoning tokens."
                )
            if finish_reason == "content_filter":
                raise RuntimeError("Provider blocked the response with its content filter.")
            raise RuntimeError(
                "Provider returned an empty chat-completion payload"
                + (f" (finish_reason={finish_reason})" if finish_reason else "")
            )
        usage = payload.get("usage") or {}
        return ProviderResponse(
            content=str(content).strip(),
            model_name=str(payload.get("model") or self.model_name),
            input_tokens=_int_or_none(usage.get("prompt_tokens")),
            output_tokens=_int_or_none(usage.get("completion_tokens")),
            total_tokens=_int_or_none(usage.get("total_tokens")),
            latency_ms=latency_ms,
            metadata={
                "provider_request_id": payload.get("id"),
                "credential_index": credential_index,
                "finish_reason": finish_reason,
            },
        )

    async def complete(self, *, system: str, user: str, max_output_tokens: int) -> ProviderResponse:
        return await asyncio.to_thread(
            self._sync_complete,
            system=system,
            user=user,
            max_output_tokens=max_output_tokens,
        )


class StaticProvider:
    """Deterministic provider used only by tests and local development harnesses."""

    key = "static"
    model_name = "static-test-model"

    def __init__(self, response: str) -> None:
        self.response = response

    async def complete(self, *, system: str, user: str, max_output_tokens: int) -> ProviderResponse:
        return ProviderResponse(
            content=self.response,
            model_name=self.model_name,
            input_tokens=max(1, (len(system) + len(user)) // 4),
            output_tokens=max(1, len(self.response) // 4),
            total_tokens=max(1, (len(system) + len(user) + len(self.response)) // 4),
            latency_ms=1,
        )


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class ProviderRegistry:
    def __init__(self, providers: dict[str, AIProvider] | None = None) -> None:
        self.providers = providers or {}

    @classmethod
    def from_settings(cls, settings: Settings) -> "ProviderRegistry":
        providers: dict[str, AIProvider] = {}
        if settings.ai_enabled and settings.ai_local_enabled and settings.ai_local_base_url and settings.ai_local_model:
            providers["local"] = OpenAICompatibleProvider(
                key="local",
                base_url=settings.ai_local_base_url,
                model_name=settings.ai_local_model,
                api_key=settings.ai_local_api_key,
                timeout_seconds=settings.ai_request_timeout_seconds,
            )
        if (
            settings.ai_enabled
            and settings.ai_remote_enabled
            and settings.ai_remote_base_url
            and settings.ai_remote_model
            and settings.ai_remote_api_key
        ):
            providers["remote"] = OpenAICompatibleProvider(
                key="remote",
                base_url=settings.ai_remote_base_url,
                model_name=settings.ai_remote_model,
                api_key=settings.ai_remote_api_key,
                timeout_seconds=settings.ai_request_timeout_seconds,
                fallback_api_keys=settings.ai_remote_fallback_api_keys,
            )
        return cls(providers)

    def get(self, key: str | None) -> AIProvider | None:
        if not key:
            return None
        return self.providers.get(key)
