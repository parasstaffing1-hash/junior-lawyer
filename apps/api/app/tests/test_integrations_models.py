from app.db.base import Base
from app import models  # noqa: F401
from app.models.integrations import IntegrationConnection, IntegrationProvider, IntegrationStatus
from uuid import uuid4


def test_batch25_schema_count_and_tables():
    names = set(Base.metadata.tables)
    assert len(names) == 250
    expected = {
        "integration_connections", "integration_secret_references", "integration_oauth_states",
        "integration_accounts", "integration_sync_runs", "integration_resource_mappings",
        "integration_webhook_endpoints", "integration_webhook_events",
        "integration_delivery_attempts", "integration_health_checks",
    }
    assert expected <= names


def test_connection_defaults_are_provider_explicit():
    row = IntegrationConnection(
        organization_id=uuid4(), connection_key="google-primary", display_name="Primary Google",
        provider=IntegrationProvider.GOOGLE_WORKSPACE, created_by_membership_id=uuid4(),
    )
    assert row.provider == IntegrationProvider.GOOGLE_WORKSPACE
    assert row.status is None or row.status == IntegrationStatus.DRAFT
