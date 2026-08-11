from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass
from types import SimpleNamespace
from datetime import date
from typing import Any

from app.models.procedure import DayBasis, DeadlineAdjustment
from app.services.evidence.classifier import classify_evidence
from app.services.language.normalizer import extract_legal_references, normalize_legal_text
from app.services.procedure.calculator import calculate_deadline
from app.services.case_lookup.parser import parse_case_query
from app.services.remedies.engine import evaluate_rule
from app.services.research.citations import parse_citations


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    passed: bool
    score: float
    actual: dict[str, Any]
    details: dict[str, Any]
    findings: tuple[dict[str, Any], ...] = ()
    duration_ms: int = 0


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _finish(started: float, passed: bool, score: float, actual: dict, details: dict, findings: list[dict] | None = None) -> EvaluationOutcome:
    return EvaluationOutcome(
        passed=bool(passed),
        score=max(0.0, min(1.0, float(score))),
        actual=actual,
        details=details,
        findings=tuple(findings or []),
        duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
    )


def evaluate_generic(evaluator: str, input_json: dict, expected_json: dict) -> EvaluationOutcome:
    started = time.perf_counter()
    actual_value = input_json.get("actual")

    if evaluator == "exact":
        expected = expected_json.get("value")
        passed = actual_value == expected
        return _finish(started, passed, 1.0 if passed else 0.0, {"value": actual_value}, {"expected": expected})

    if evaluator == "text_exact":
        expected = expected_json.get("value", "")
        actual = _norm(actual_value)
        target = _norm(expected)
        passed = actual == target
        return _finish(started, passed, 1.0 if passed else 0.0, {"value": actual_value}, {"normalized_actual": actual, "normalized_expected": target})

    if evaluator == "contains_all":
        text = _norm(actual_value)
        required = [_norm(v) for v in expected_json.get("values", [])]
        missing = [v for v in required if v and v not in text]
        score = 1.0 if not required else (len(required) - len(missing)) / len(required)
        return _finish(started, not missing, score, {"value": actual_value}, {"missing": missing, "required": required})

    if evaluator == "forbidden_absent":
        text = _norm(actual_value)
        forbidden = [_norm(v) for v in expected_json.get("values", [])]
        leaked = [v for v in forbidden if v and v in text]
        return _finish(
            started,
            not leaked,
            1.0 if not leaked else 0.0,
            {"value": actual_value},
            {"leaked": leaked},
            [{"code": "SECURITY_LEAK", "severity": "critical", "message": f"Forbidden value leaked: {value}"} for value in leaked],
        )

    if evaluator == "numeric_tolerance":
        expected = float(expected_json.get("value", 0.0))
        tolerance = float(expected_json.get("tolerance", 0.0))
        actual = float(actual_value)
        delta = abs(actual - expected)
        passed = delta <= tolerance
        score = 1.0 if passed else max(0.0, 1.0 - delta / max(abs(expected), 1.0))
        return _finish(started, passed, score, {"value": actual}, {"expected": expected, "tolerance": tolerance, "delta": delta})

    if evaluator == "rank_at_k":
        ranked = list(input_json.get("ranked_ids", []))
        relevant = list(expected_json.get("relevant_ids", []))
        k = max(1, int(expected_json.get("k", 5)))
        hits = [item for item in ranked[:k] if item in relevant]
        recall = 1.0 if not relevant else len(set(hits)) / len(set(relevant))
        min_recall = float(expected_json.get("min_recall", 1.0))
        return _finish(started, recall >= min_recall, recall, {"ranked_ids": ranked[:k]}, {"relevant_ids": relevant, "k": k, "recall": recall, "min_recall": min_recall})

    if evaluator == "provenance_complete":
        claims = list(input_json.get("claims", []))
        total = len(claims)
        sourced = sum(1 for claim in claims if claim.get("source_ids"))
        coverage = 1.0 if total == 0 else sourced / total
        minimum = float(expected_json.get("min_coverage", 1.0))
        return _finish(started, coverage >= minimum, coverage, {"claims": claims}, {"coverage": coverage, "min_coverage": minimum})

    raise ValueError(f"Unknown evaluator: {evaluator}")


def evaluate_probe(evaluator: str, input_json: dict, expected_json: dict) -> EvaluationOutcome:
    started = time.perf_counter()

    if evaluator == "language_normalization":
        text = str(input_json.get("text", ""))
        normalized = normalize_legal_text(text)
        refs = [ref.canonical for ref in extract_legal_references(text)]
        expected_normalized_contains = [_norm(v) for v in expected_json.get("normalized_contains", [])]
        missing = [v for v in expected_normalized_contains if v not in _norm(normalized)]
        expected_refs = set(expected_json.get("references", []))
        missing_refs = sorted(expected_refs - set(refs))
        passed = not missing and not missing_refs
        denom = max(1, len(expected_normalized_contains) + len(expected_refs))
        score = 1.0 - (len(missing) + len(missing_refs)) / denom
        return _finish(started, passed, score, {"normalized": normalized, "references": refs}, {"missing_terms": missing, "missing_references": missing_refs})

    if evaluator == "citation_parser":
        text = str(input_json.get("text", ""))
        parsed = [item.normalized for item in parse_citations(text)]
        expected = [str(v).upper() for v in expected_json.get("citations", [])]
        missing = [value for value in expected if value not in parsed]
        unexpected = [value for value in parsed if value not in expected] if expected_json.get("reject_extra") else []
        passed = not missing and not unexpected
        denom = max(1, len(expected) + len(unexpected))
        score = max(0.0, 1.0 - (len(missing) + len(unexpected)) / denom)
        return _finish(started, passed, score, {"citations": parsed}, {"missing": missing, "unexpected": unexpected})

    if evaluator == "deadline_calculator":
        trigger = date.fromisoformat(str(input_json["trigger_date"]))
        holidays = {date.fromisoformat(str(v)) for v in input_json.get("holidays", [])}
        result = calculate_deadline(
            trigger,
            offset_days=int(input_json.get("offset_days", 0)),
            day_basis=DayBasis(str(input_json.get("day_basis", DayBasis.CALENDAR.value))),
            count_from_next_day=bool(input_json.get("count_from_next_day", True)),
            adjustment=DeadlineAdjustment(str(input_json.get("adjustment", DeadlineAdjustment.NONE.value))),
            holidays=holidays,
        ).as_dict()
        expected_due = str(expected_json.get("due_date"))
        passed = result["due_date"] == expected_due
        return _finish(started, passed, 1.0 if passed else 0.0, result, {"expected_due_date": expected_due})

    if evaluator == "evidence_classifier":
        result = classify_evidence(str(input_json.get("filename", "")), str(input_json.get("text", "")))
        expected_kind = str(expected_json.get("kind", ""))
        passed = result.kind.value == expected_kind
        return _finish(started, passed, 1.0 if passed else 0.0, {"kind": result.kind.value, "confidence": result.confidence, "matched_terms": list(result.matched_terms)}, {"expected_kind": expected_kind, "classifier_confidence": result.confidence})

    if evaluator == "ocr_text_quality":
        expected_text = _norm(expected_json.get("text", ""))
        actual_text = _norm(input_json.get("ocr_text", ""))
        if not expected_text:
            return _finish(started, True, 1.0, {"ocr_text": input_json.get("ocr_text", "")}, {"similarity": 1.0})
        expected_tokens = expected_text.split()
        actual_tokens = actual_text.split()
        # Deterministic token recall is deliberately simple and explainable.
        remaining = list(actual_tokens)
        hits = 0
        for token in expected_tokens:
            if token in remaining:
                hits += 1
                remaining.remove(token)
        recall = hits / len(expected_tokens)
        threshold = float(expected_json.get("min_token_recall", 0.95))
        return _finish(started, recall >= threshold, recall, {"ocr_text": input_json.get("ocr_text", "")}, {"token_recall": recall, "threshold": threshold})

    if evaluator == "json_contract":
        actual = input_json.get("actual", {})
        required_keys = list(expected_json.get("required_keys", []))
        missing = [key for key in required_keys if key not in actual]
        return _finish(started, not missing, 1.0 if not missing else max(0.0, 1.0 - len(missing) / max(1, len(required_keys))), {"actual": actual}, {"missing_keys": missing})

    if evaluator == "case_query_parser":
        parsed = parse_case_query(str(input_json.get("query", ""))).as_dict()
        expected = dict(expected_json.get("parsed") or expected_json)
        mismatches = {key: {"expected": value, "actual": parsed.get(key)} for key, value in expected.items() if parsed.get(key) != value}
        return _finish(started, not mismatches, 1.0 if not mismatches else 0.0, parsed, {"mismatches": mismatches})

    if evaluator == "remedy_rule":
        rule_spec = dict(input_json.get("rule") or {})
        rule = SimpleNamespace(
            case_stage_patterns_json=list(rule_spec.get("case_stage_patterns_json") or []),
            status_patterns_json=list(rule_spec.get("status_patterns_json") or []),
            court_level_patterns_json=list(rule_spec.get("court_level_patterns_json") or []),
            order_type_patterns_json=list(rule_spec.get("order_type_patterns_json") or []),
            act_patterns_json=list(rule_spec.get("act_patterns_json") or []),
            section_patterns_json=list(rule_spec.get("section_patterns_json") or []),
            requires_final_order=bool(rule_spec.get("requires_final_order", False)),
            requires_latest_order=bool(rule_spec.get("requires_latest_order", False)),
            maintainability_json=dict(rule_spec.get("maintainability_json") or {}),
            limitation_json=dict(rule_spec.get("limitation_json") or {}),
            priority=int(rule_spec.get("priority", 50)),
        )
        as_of_raw = input_json.get("as_of_date")
        result = evaluate_rule(rule, dict(input_json.get("context") or {}), as_of_date=date.fromisoformat(str(as_of_raw)) if as_of_raw else None)
        actual = {"matched": result is not None}
        if result:
            actual.update({"status": result.get("status"), "score": result.get("score"), "deadline": result.get("deadline"), "maintainability": result.get("maintainability")})
        expected_match = bool(expected_json.get("matched", True))
        passed = actual["matched"] is expected_match
        if passed and result is not None and expected_json.get("status") is not None:
            passed = result.get("status") == expected_json.get("status")
        if passed and result is not None and expected_json.get("due_date") is not None:
            passed = result.get("deadline", {}).get("due_date") == expected_json.get("due_date")
        return _finish(started, passed, 1.0 if passed else 0.0, actual, {"expected": expected_json})

    return evaluate_generic(evaluator, input_json, expected_json)


def category_scores(rows: list[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        grouped.setdefault(str(row["category"]), []).append((float(row.get("score", 0.0)), float(row.get("weight", 1.0))))
    output: dict[str, float] = {}
    for category, values in grouped.items():
        total_weight = sum(max(0.0, weight) for _, weight in values)
        output[category] = 0.0 if total_weight <= 0 else sum(score * max(0.0, weight) for score, weight in values) / total_weight
    return output


def evaluate_release_gate(
    *,
    overall_score: float,
    critical_failures: int,
    category_scores_map: dict[str, float],
    gate: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    minimum = float(gate.get("min_overall_score", 0.90))
    if overall_score < minimum:
        reasons.append(f"Overall score {overall_score:.3f} is below {minimum:.3f}")
    max_critical = int(gate.get("max_critical_failures", 0))
    if critical_failures > max_critical:
        reasons.append(f"Critical failures {critical_failures} exceed allowed {max_critical}")
    thresholds = dict(gate.get("category_thresholds_json", {}))
    for category, threshold in sorted(thresholds.items()):
        actual = category_scores_map.get(category)
        if actual is None:
            reasons.append(f"Required category {category} has no evaluation cases")
        elif actual < float(threshold):
            reasons.append(f"Category {category} score {actual:.3f} is below {float(threshold):.3f}")
    if gate.get("require_security_zero_failures", True) and category_scores_map.get("security", 1.0) < 1.0:
        reasons.append("Security category contains a failure")
    if gate.get("require_citation_zero_failures", True) and category_scores_map.get("citation", 1.0) < 1.0:
        reasons.append("Citation category contains a failure")
    return not reasons, reasons
