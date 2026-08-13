from app import models  # noqa: F401
from app.db.base import Base


def test_batch28_schema_contains_release_candidate_validation_tables():
    names = set(Base.metadata.tables)
    assert len(names) == 255
    assert {
        "validation_campaigns",
        "validation_scenarios",
        "validation_scenario_runs",
        "validation_evidence",
        "release_candidate_manifests",
        "pilot_readiness_checks",
        "validation_signoffs",
        "validation_datasets",
    }.issubset(names)
