from sqlalchemy import create_engine

from app import models  # noqa: F401
from app.db.base import Base


def test_batch21_system_health_tables_registered():
    expected = {
        "system_health_runs", "system_health_components", "system_incidents", "system_incident_events",
        "backup_policies", "backup_runs", "backup_artifacts", "restore_drills", "recovery_objectives",
        "system_metric_snapshots",
    }
    assert expected <= set(Base.metadata.tables)
    assert len(Base.metadata.tables) == 255


def test_batch21_schema_creates_on_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        names = set(engine.dialect.get_table_names(connection))
    assert "backup_runs" in names
    assert "system_metric_snapshots" in names
    assert len(names) == 255
