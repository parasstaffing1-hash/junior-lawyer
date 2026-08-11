from app import models  # noqa: F401
from app.db.base import Base


def test_operations_tables_registered():
    expected = {
        "workflow_templates", "workflow_events", "workflow_runs", "workflow_tasks",
        "workflow_notifications", "workflow_escalations", "court_case_trackers",
        "court_case_snapshots", "court_case_changes", "operations_preferences",
    }
    assert expected <= set(Base.metadata.tables)
