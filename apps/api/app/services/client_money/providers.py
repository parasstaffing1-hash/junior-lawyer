from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.models.client_money import PaymentIntentStatus, PaymentProviderKind


@dataclass(frozen=True, slots=True)
class ProviderIntentResult:
    status: PaymentIntentStatus
    provider_reference: str | None
    checkout_url: str | None


class PaymentProviderAdapter:
    kind: PaymentProviderKind

    def create_intent(self, intent_id: str) -> ProviderIntentResult:
        raise NotImplementedError


class ManualProvider(PaymentProviderAdapter):
    kind = PaymentProviderKind.MANUAL

    def create_intent(self, intent_id: str) -> ProviderIntentResult:
        return ProviderIntentResult(PaymentIntentStatus.CREATED, f"manual-{intent_id}", None)


class MockProvider(PaymentProviderAdapter):
    kind = PaymentProviderKind.MOCK

    def create_intent(self, intent_id: str) -> ProviderIntentResult:
        ref = f"mock-{uuid4().hex[:16]}"
        return ProviderIntentResult(PaymentIntentStatus.PENDING, ref, f"https://example.invalid/pay/{ref}")


def provider_adapter(kind: PaymentProviderKind) -> PaymentProviderAdapter:
    if kind == PaymentProviderKind.MANUAL:
        return ManualProvider()
    if kind == PaymentProviderKind.MOCK:
        return MockProvider()
    raise NotImplementedError(f"Provider {kind.value} requires an explicit production connector")
