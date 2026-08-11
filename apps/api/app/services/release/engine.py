from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from statistics import median
from typing import Iterable, Sequence


def canonical_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    q = min(1.0, max(0.0, float(q)))
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize_latencies(latencies_ms: Sequence[float], *, success_count: int, failure_count: int, duration_seconds: float) -> dict:
    total = max(0, int(success_count)) + max(0, int(failure_count))
    duration = max(float(duration_seconds), 1e-9)
    error_rate = (failure_count / total) if total else 0.0
    success_rate = (success_count / total) if total else 0.0
    return {
        "total_requests": total,
        "successful_requests": max(0, int(success_count)),
        "failed_requests": max(0, int(failure_count)),
        "requests_per_second": total / duration,
        "success_rate": success_rate,
        "error_rate": error_rate,
        "p50_ms": percentile(latencies_ms, 0.50),
        "p95_ms": percentile(latencies_ms, 0.95),
        "p99_ms": percentile(latencies_ms, 0.99),
        "max_ms": max(latencies_ms) if latencies_ms else 0.0,
        "median_ms": median(latencies_ms) if latencies_ms else 0.0,
    }


def evaluate_performance(metrics: dict, *, max_p95_ms: float, min_success_rate: float, max_error_rate: float) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    p95 = float(metrics.get("p95_ms") or 0.0)
    success_rate = float(metrics.get("success_rate") or 0.0)
    error_rate = float(metrics.get("error_rate") or 0.0)
    if p95 > max_p95_ms:
        reasons.append(f"p95 latency {p95:.1f}ms exceeds {max_p95_ms:.1f}ms")
    if success_rate < min_success_rate:
        reasons.append(f"success rate {success_rate:.3f} below {min_success_rate:.3f}")
    if error_rate > max_error_rate:
        reasons.append(f"error rate {error_rate:.3f} exceeds {max_error_rate:.3f}")
    return not reasons, reasons


def evaluate_security_result(actual: dict, expected: dict) -> tuple[bool, list[str]]:
    """Evaluate safe, explicit assertions from a security probe result.

    The evaluator intentionally avoids arbitrary expressions/code execution. Supported expectations:
    - status_in: list[int]
    - forbidden_strings_absent: list[str]
    - required_headers: dict[str, str|None] (None means header must exist)
    - body_contains: list[str]
    - body_not_contains: list[str]
    - json_equals: dict of shallow keys
    """
    reasons: list[str] = []
    status = actual.get("status_code")
    body = str(actual.get("body") or "")
    headers = {str(k).casefold(): str(v) for k, v in dict(actual.get("headers") or {}).items()}
    json_payload = actual.get("json") if isinstance(actual.get("json"), dict) else {}

    allowed = expected.get("status_in")
    if allowed is not None and status not in set(int(v) for v in allowed):
        reasons.append(f"HTTP status {status} not in {list(allowed)}")

    for needle in expected.get("forbidden_strings_absent") or []:
        if str(needle).casefold() in body.casefold():
            reasons.append(f"forbidden output leaked: {needle}")

    for needle in expected.get("body_contains") or []:
        if str(needle).casefold() not in body.casefold():
            reasons.append(f"expected body text missing: {needle}")

    for needle in expected.get("body_not_contains") or []:
        if str(needle).casefold() in body.casefold():
            reasons.append(f"disallowed body text present: {needle}")

    for key, value in dict(expected.get("required_headers") or {}).items():
        actual_value = headers.get(str(key).casefold())
        if actual_value is None:
            reasons.append(f"required header missing: {key}")
        elif value is not None and str(value).casefold() not in actual_value.casefold():
            reasons.append(f"header {key} does not contain expected value")

    for key, value in dict(expected.get("json_equals") or {}).items():
        if json_payload.get(key) != value:
            reasons.append(f"JSON field {key} mismatch")

    return not reasons, reasons


@dataclass(frozen=True)
class ReleaseGateInput:
    backend_tests_passed: bool
    qa_passed: bool | None
    security_passed: bool | None
    load_passed: bool | None
    migration_passed: bool | None
    frontend_passed: bool | None
    critical_security_failures: int = 0
    rollback_ready: bool = False
    artifact_passed: bool = False


def decide_release_gate(
    gate: ReleaseGateInput,
    *,
    require_qa_gate: bool = True,
    require_security_zero_critical: bool = True,
    require_migration_roundtrip: bool = True,
    require_frontend_static: bool = True,
    require_load_gate: bool = True,
    require_rollback_point: bool = True,
    require_artifact_integrity: bool = True,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not gate.backend_tests_passed:
        reasons.append("backend test gate failed")
    if require_qa_gate and gate.qa_passed is not True:
        reasons.append("legal QA gate not passed")
    if require_security_zero_critical:
        if gate.security_passed is not True:
            reasons.append("security gate not passed")
        if gate.critical_security_failures:
            reasons.append(f"{gate.critical_security_failures} critical security failure(s)")
    if require_load_gate and gate.load_passed is not True:
        reasons.append("performance/load gate not passed")
    if require_migration_roundtrip and gate.migration_passed is not True:
        reasons.append("migration round-trip gate not passed")
    if require_frontend_static and gate.frontend_passed is not True:
        reasons.append("frontend static gate not passed")
    if require_rollback_point and not gate.rollback_ready:
        reasons.append("verified rollback point missing")
    if require_artifact_integrity and not gate.artifact_passed:
        reasons.append("release artifact integrity gate not passed")
    return not reasons, reasons


def build_release_manifest(*, app_version: str, build_ref: str | None, database_revision: str | None, artifact_hashes: Iterable[dict], gates: dict) -> dict:
    artifacts = sorted(
        ({"kind": str(item.get("kind")), "filename": str(item.get("filename")), "sha256": str(item.get("sha256"))} for item in artifact_hashes),
        key=lambda item: (item["kind"], item["filename"]),
    )
    payload = {
        "app_version": app_version,
        "build_ref": build_ref,
        "database_revision": database_revision,
        "artifacts": artifacts,
        "gates": gates,
    }
    return {**payload, "snapshot_hash": canonical_hash(payload)}


def safe_release_filename(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value.strip())
    cleaned = cleaned.strip("-.")
    return cleaned[:160] or "release"
