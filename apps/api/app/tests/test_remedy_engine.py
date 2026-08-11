from datetime import date
from types import SimpleNamespace

from app.services.remedies.engine import evaluate_limitation, evaluate_rule, research_hints


def rule(**overrides):
    values = dict(
        case_stage_patterns_json=[], status_patterns_json=[], court_level_patterns_json=[], order_type_patterns_json=[],
        act_patterns_json=[], section_patterns_json=[], requires_final_order=False, requires_latest_order=False,
        maintainability_json={}, limitation_json={}, priority=60,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_verified_rule_shape_matches_case_stage_deterministically():
    result = evaluate_rule(rule(case_stage_patterns_json=["arguments"]), {"case_stage":"Final Arguments", "orders":[], "judgments":[]}, as_of_date=date(2026,8,8))
    assert result is not None
    assert result["status"] == "possible"
    assert result["score"] >= 50


def test_rule_is_not_returned_when_required_stage_does_not_match():
    assert evaluate_rule(rule(case_stage_patterns_json=["evidence"]), {"case_stage":"Arguments", "orders":[], "judgments":[]}) is None


def test_final_order_requirement_is_enforced():
    assert evaluate_rule(rule(requires_final_order=True), {"status":"Pending", "case_stage":"Evidence", "orders":[], "judgments":[]}) is None
    assert evaluate_rule(rule(requires_final_order=True), {"status":"Disposed", "case_stage":"Judgment", "orders":[], "judgments":[{"decision_date":"2026-08-01"}]}) is not None


def test_deadline_uses_rule_trigger_without_inventing_missing_date():
    missing = evaluate_limitation({"days":30,"trigger":"latest_order_date"}, {"orders":[],"judgments":[]}, as_of_date=date(2026,8,8))
    assert missing["calculated"] is False
    assert missing["status"] == "needs_review"
    known = evaluate_limitation({"days":30,"trigger":"latest_order_date","day_basis":"calendar"}, {"orders":[{"order_date":"2026-08-01"}]}, as_of_date=date(2026,8,8))
    assert known["calculated"] is True
    assert known["due_date"] == "2026-08-31"


def test_research_hints_are_explicitly_not_maintainability_conclusions():
    hints = research_hints({"status":"Disposed", "case_stage":"Judgment", "orders":[{"order_date":"2026-08-01"}], "judgments":[]})
    assert any(item["code"] == "appeal_review_revision" for item in hints)
    assert any("must be verified" in item["reason"] or "verify" in item["reason"].casefold() for item in hints)
