from app.db.base import Base
from app.models import *  # noqa: F401,F403
from app.models.evidence import EvidenceKind, EvidenceReviewStatus, EvidenceStrength, GapStatus


def test_batch15_schema_tables_present():
    expected = {
        "litigation_issues", "evidence_items", "evidence_issue_links", "evidence_witnesses",
        "evidence_witness_links", "evidence_gaps", "evidence_bundles", "evidence_bundle_items",
        "evidence_exhibits", "witness_prep_questions",
    }
    assert expected.issubset(Base.metadata.tables)


def test_evidence_enum_values_are_stable():
    assert EvidenceKind.CONTRACT.value == "contract"
    assert EvidenceStrength.HIGH.value == "high"
    assert EvidenceReviewStatus.REVIEWED.value == "reviewed"
    assert GapStatus.OPEN.value == "open"
