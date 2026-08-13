from app import models  # noqa: F401
from app.db.base import Base
from app.models.release import (
    PerformanceScenarioKind,
    ReleaseRunStatus,
    SecurityCheckKind,
)


def test_release_tables_expand_schema():
    names = set(Base.metadata.tables)
    assert len(names) == 252
    required = {
        "release_pipelines",
        "release_runs",
        "release_stage_runs",
        "performance_scenarios",
        "performance_runs",
        "security_test_cases",
        "security_test_runs",
        "release_artifacts",
        "rollback_points",
        "deployment_approvals",
    }
    assert required.issubset(names)


def test_release_enums_are_stable_strings():
    assert ReleaseRunStatus.HELD.value == "held"
    assert PerformanceScenarioKind.SEARCH_CONCURRENCY.value == "search_concurrency"
    assert SecurityCheckKind.ETHICAL_WALL.value == "ethical_wall"
