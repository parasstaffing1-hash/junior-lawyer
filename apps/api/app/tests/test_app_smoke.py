"""Assembly smoke tests.

Every other suite exercises services and models in isolation, so a fatal
ImportError in `app.main` survived the full release gate: nothing imported the
assembled application. These tests are deliberately cheap and cover the gap.

TestClient is used *without* the context manager on purpose. Entering the
context manager runs the lifespan handler, which calls `Base.metadata.create_all`
when `app_env` is "development". Plain request calls skip lifespan entirely, so
these tests never touch a database.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_responds() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_schema_generates() -> None:
    """Catches unresolvable response models and duplicate operation ids across
    every router, which unit tests never see."""
    schema = app.openapi()
    assert schema["info"]["title"]
    assert schema["paths"]


def test_expected_routers_are_mounted() -> None:
    paths = set(app.openapi()["paths"])
    for expected in (
        "/api/v1/matters",
        "/api/v1/research/search",
        "/api/v1/case-lookup/search",
        "/api/v1/remedies/analyze",
    ):
        assert any(path.startswith(expected) for path in paths), f"missing route: {expected}"
