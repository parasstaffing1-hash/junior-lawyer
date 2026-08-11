from sqlalchemy import create_engine
from app.db.base import Base
from app import models  # noqa: F401


def test_crm_tables_are_registered():
    expected = {
        "crm_leads", "clients", "client_contacts", "conflict_checks", "conflict_candidates",
        "client_onboarding", "client_kyc_records", "engagements", "matter_client_links",
        "client_notes", "crm_tasks", "client_communications", "time_entries", "client_portal_access", "client_security_profiles", "client_access_grants",
    }
    assert expected <= set(Base.metadata.tables)


def test_schema_creates_with_crm_tables():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    names = set(engine.dialect.get_table_names(engine.connect()))
    assert "clients" in names
    assert "conflict_checks" in names
    assert "time_entries" in names
