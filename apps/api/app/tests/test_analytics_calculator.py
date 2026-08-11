from app.models.analytics import AnalyticsRiskSeverity, GoalComparison
from app.services.analytics.calculator import (
    MatterHealthInput,
    classify_health,
    collection_age_bucket,
    goal_progress,
    matter_health_score,
    percentage,
    stable_payload_hash,
    workload_score,
)


def test_clean_matter_health_is_100():
    score, reasons = matter_health_score(MatterHealthInput())
    assert score == 100
    assert reasons == []


def test_matter_health_penalties_are_explainable_and_capped():
    score, reasons = matter_health_score(MatterHealthInput(overdue_tasks=50, open_contradictions=1))
    assert score == 60
    assert reasons[0]["key"] == "overdue_tasks"
    assert reasons[0]["penalty"] == 30.0
    assert reasons[1]["penalty"] == 10.0


def test_custom_health_weights_are_used():
    score, reasons = matter_health_score(MatterHealthInput(overdue_tasks=1), {"overdue_task": 5})
    assert score == 95
    assert reasons[0]["weight"] == 5


def test_health_classification_boundaries():
    assert classify_health(95) == AnalyticsRiskSeverity.INFO
    assert classify_health(80) == AnalyticsRiskSeverity.LOW
    assert classify_health(65) == AnalyticsRiskSeverity.MEDIUM
    assert classify_health(50) == AnalyticsRiskSeverity.HIGH
    assert classify_health(20) == AnalyticsRiskSeverity.CRITICAL


def test_workload_score_prioritizes_overdue_and_high_work():
    normal = workload_score(open_tasks=10, overdue_tasks=0, high_priority_tasks=0)
    risky = workload_score(open_tasks=10, overdue_tasks=2, high_priority_tasks=3)
    assert normal == 30
    assert risky > normal
    assert risky <= 100


def test_percentage_is_zero_safe_and_decimal_stable():
    assert percentage(5, 0) == 0.0
    assert percentage(1, 3) == 33.3


def test_collection_age_buckets():
    assert collection_age_bucket(-1) == "current"
    assert collection_age_bucket(0) == "current"
    assert collection_age_bucket(30) == "1_30"
    assert collection_age_bucket(31) == "31_60"
    assert collection_age_bucket(61) == "61_90"
    assert collection_age_bucket(91) == "90_plus"


def test_goal_progress_at_least():
    pct, met = goal_progress(80, 100, GoalComparison.AT_LEAST)
    assert pct == 80.0 and met is False
    pct, met = goal_progress(120, 100, GoalComparison.AT_LEAST)
    assert pct == 100.0 and met is True


def test_goal_progress_at_most():
    pct, met = goal_progress(2, 5, GoalComparison.AT_MOST)
    assert pct == 100.0 and met is True
    pct, met = goal_progress(10, 5, GoalComparison.AT_MOST)
    assert pct == 50.0 and met is False


def test_snapshot_hash_is_order_independent():
    assert stable_payload_hash({"a": 1, "b": 2}) == stable_payload_hash({"b": 2, "a": 1})
    assert stable_payload_hash({"a": 1}) != stable_payload_hash({"a": 2})
