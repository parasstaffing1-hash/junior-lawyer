from sqlalchemy import create_engine

from app.db.base import Base
import app.models  # noqa: F401
from app.models.analytics import AnalyticsRiskStatus, AnalyticsScope, GoalComparison, SnapshotKind


def test_batch17_analytics_tables_registered():
    expected = {
        "analytics_metric_definitions",
        "analytics_preferences",
        "analytics_snapshots",
        "analytics_metric_values",
        "matter_health_snapshots",
        "member_performance_snapshots",
        "client_health_snapshots",
        "analytics_risk_signals",
        "analytics_goals",
        "analytics_goal_progress",
    }
    assert expected <= set(Base.metadata.tables)
    assert len(Base.metadata.tables) == 255


def test_batch17_schema_creates_on_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    names = set(engine.dialect.get_table_names(engine.connect()))
    assert "analytics_snapshots" in names
    assert "analytics_risk_signals" in names
    assert len(names) == 255


def test_batch17_enum_values_are_stable():
    assert AnalyticsScope.MATTER.value == "matter"
    assert AnalyticsRiskStatus.ACKNOWLEDGED.value == "acknowledged"
    assert GoalComparison.AT_MOST.value == "at_most"
    assert SnapshotKind.MONTHLY.value == "monthly"
