from app import models  # noqa: F401
from app.db.base import Base


def test_qa_tables_present():
    names = set(Base.metadata.tables)
    required = {
        "evaluation_suites",
        "evaluation_cases",
        "evaluation_runs",
        "evaluation_case_runs",
        "evaluation_metrics",
        "release_quality_gates",
        "release_quality_gate_runs",
        "qa_findings",
        "evaluation_baselines",
    }
    assert required <= names
    assert len(names) == 250
