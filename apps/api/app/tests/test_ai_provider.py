import pytest

from app.services.ai.providers import ProviderRegistry, StaticProvider


@pytest.mark.asyncio
async def test_static_provider_is_deterministic():
    provider = StaticProvider("Answer [S1]")
    result = await provider.complete(system="system", user="user", max_output_tokens=100)
    assert result.content == "Answer [S1]"
    assert result.model_name == "static-test-model"
    assert result.total_tokens


def test_registry_returns_only_registered_provider():
    registry = ProviderRegistry({"local": StaticProvider("x")})
    assert registry.get("local") is not None
    assert registry.get("remote") is None
