from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import Settings


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
    ) -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _sync_complete(self, *, system: str, user: str, max_output_tokens: int) -> ProviderResponse:
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
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, headers=headers, method="POST"
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"Provider HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Provider connection failed: {exc.reason}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Provider returned an unsupported chat-completion payload") from exc
        usage = payload.get("usage") or {}
        return ProviderResponse(
            content=str(content).strip(),
            model_name=str(payload.get("model") or self.model_name),
            input_tokens=_int_or_none(usage.get("prompt_tokens")),
            output_tokens=_int_or_none(usage.get("completion_tokens")),
            total_tokens=_int_or_none(usage.get("total_tokens")),
            latency_ms=latency_ms,
            metadata={"provider_request_id": payload.get("id")},
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
            )
        return cls(providers)

    def get(self, key: str | None) -> AIProvider | None:
        if not key:
            return None
        return self.providers.get(key)
