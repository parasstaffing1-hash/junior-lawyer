from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping

from app.models.analytics import AnalyticsRiskSeverity, GoalComparison


DEFAULT_HEALTH_WEIGHTS = {
    "overdue_task": 12,
    "high_priority_task": 4,
    "deadline_due_7d": 8,
    "open_contradiction": 10,
    "open_high_draft_finding": 8,
    "unreviewed_court_change": 6,
    "open_evidence_gap": 7,
}

DEFAULT_THRESHOLDS = {
    "matter_health_high_risk": 60,
    "matter_health_critical": 40,
    "overdue_tasks_high": 3,
    "member_workload_high": 70,
    "invoice_overdue_days_high": 30,
    "client_overdue_amount_high": 100000,
}


@dataclass(frozen=True, slots=True)
class MatterHealthInput:
    overdue_tasks: int = 0
    high_priority_tasks: int = 0
    deadlines_due_7d: int = 0
    open_contradictions: int = 0
    open_high_draft_findings: int = 0
    unreviewed_court_changes: int = 0
    open_evidence_gaps: int = 0


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def matter_health_score(values: MatterHealthInput, weights: Mapping[str, float] | None = None) -> tuple[int, list[dict]]:
    active = {**DEFAULT_HEALTH_WEIGHTS, **(dict(weights or {}))}
    penalties = [
        ("overdue_tasks", values.overdue_tasks, active["overdue_task"], "Overdue operational tasks"),
        ("high_priority_tasks", values.high_priority_tasks, active["high_priority_task"], "Open high-priority tasks"),
        ("deadlines_due_7d", values.deadlines_due_7d, active["deadline_due_7d"], "Reviewed deadlines due within 7 days"),
        ("open_contradictions", values.open_contradictions, active["open_contradiction"], "Open factual contradictions"),
        ("open_high_draft_findings", values.open_high_draft_findings, active["open_high_draft_finding"], "Open high drafting findings"),
        ("unreviewed_court_changes", values.unreviewed_court_changes, active["unreviewed_court_change"], "Unreviewed court changes"),
        ("open_evidence_gaps", values.open_evidence_gaps, active["open_evidence_gap"], "Open evidence gaps"),
    ]
    reasons: list[dict] = []
    total_penalty = 0.0
    for key, count, weight, label in penalties:
        if count <= 0:
            continue
        # Avoid one noisy metric making every matter zero; each category is capped at 30 points.
        penalty = min(30.0, float(count) * float(weight))
        total_penalty += penalty
        reasons.append({"key": key, "count": count, "weight": weight, "penalty": penalty, "label": label})
    return int(round(clamp(100.0 - total_penalty))), reasons


def classify_health(score: int) -> AnalyticsRiskSeverity:
    if score < 40:
        return AnalyticsRiskSeverity.CRITICAL
    if score < 60:
        return AnalyticsRiskSeverity.HIGH
    if score < 75:
        return AnalyticsRiskSeverity.MEDIUM
    if score < 90:
        return AnalyticsRiskSeverity.LOW
    return AnalyticsRiskSeverity.INFO


def workload_score(*, open_tasks: int, overdue_tasks: int, high_priority_tasks: int) -> int:
    # Transparent heuristic: open work matters, but overdue/high-priority work weighs more.
    raw = open_tasks * 3 + overdue_tasks * 14 + high_priority_tasks * 7
    return int(round(clamp(raw)))


def percentage(numerator: float | Decimal, denominator: float | Decimal) -> float:
    den = Decimal(str(denominator))
    if den == 0:
        return 0.0
    value = (Decimal(str(numerator)) / den * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return float(value)


def collection_age_bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "90_plus"


def goal_progress(actual: float, target: float, comparison: GoalComparison) -> tuple[float, bool]:
    if comparison == GoalComparison.AT_MOST:
        met = actual <= target
        if actual <= 0:
            return 100.0, met
        pct = clamp((target / actual) * 100.0)
        return round(pct, 1), met
    if comparison == GoalComparison.EXACT:
        met = actual == target
        if target == 0:
            return (100.0 if actual == 0 else 0.0), met
        distance = abs(actual - target) / abs(target)
        return round(clamp((1.0 - distance) * 100.0), 1), met
    met = actual >= target
    if target <= 0:
        return 100.0, met
    return round(clamp((actual / target) * 100.0), 1), met


def stable_payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
