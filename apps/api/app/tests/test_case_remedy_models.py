from app import models  # noqa: F401
from app.db.base import Base


def test_case_lookup_and_remedy_tables_registered():
    names = set(Base.metadata.tables)
    expected = {
        "case_lookup_preferences", "saved_cases", "saved_case_parties", "saved_case_advocates", "saved_case_acts",
        "saved_case_hearings", "saved_case_orders", "saved_case_judgments", "case_source_snapshots", "case_snapshot_changes",
        "case_lookup_runs", "case_lookup_candidates", "remedy_rule_packs", "remedy_rules", "remedy_rule_authorities",
        "remedy_analyses", "remedy_candidates", "remedy_candidate_authorities", "remedy_memos", "remedy_draft_links",
    }
    assert expected <= names
    assert len(names) == 252
