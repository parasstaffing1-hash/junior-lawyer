#!/usr/bin/env python3
"""Run Batch-22's built-in deterministic golden cases without a database.

Useful as a dependency-light CI smoke gate. Organization-specific suites remain in the DB/API.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.qa.evaluators import category_scores, canonical_hash, evaluate_probe, evaluate_release_gate
from app.services.qa.service import DEFAULT_CASES


def main() -> int:
    rows = []
    critical = 0
    for case in DEFAULT_CASES:
        outcome = evaluate_probe(case["evaluator"], case.get("input_json", {}), case.get("expected_json", {}))
        if not outcome.passed and case.get("critical"):
            critical += 1
        rows.append({
            "case_key": case["case_key"],
            "category": case["category"],
            "passed": outcome.passed,
            "score": outcome.score,
            "weight": case.get("weight", 1.0),
            "duration_ms": outcome.duration_ms,
            "details": outcome.details,
        })
    categories = category_scores(rows)
    total_weight = sum(float(row["weight"]) for row in rows) or 1.0
    overall = sum(float(row["score"]) * float(row["weight"]) for row in rows) / total_weight
    gate = {
        "min_overall_score": 0.95,
        "max_critical_failures": 0,
        "require_security_zero_failures": True,
        "require_citation_zero_failures": True,
        "category_thresholds_json": {"security": 1.0, "citation": 1.0, "deadline": 1.0, "language": 1.0, "drafting": 1.0},
    }
    passed, reasons = evaluate_release_gate(overall_score=overall, critical_failures=critical, category_scores_map=categories, gate=gate)
    payload = {
        "passed": passed,
        "overall_score": round(overall, 6),
        "critical_failures": critical,
        "category_scores": categories,
        "reasons": reasons,
        "cases": rows,
    }
    payload["snapshot_hash"] = canonical_hash(payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
