from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable


def canonical_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def value_of(value: object) -> str:
    return str(getattr(value, "value", value))


@dataclass(frozen=True)
class ScenarioGateRow:
    key: str
    severity: str
    status: str


@dataclass(frozen=True)
class PilotGateRow:
    key: str
    required: bool
    status: str


def evaluate_validation_gate(
    scenarios: Iterable[ScenarioGateRow],
    checks: Iterable[PilotGateRow],
    *,
    release_approved: bool,
    rollback_verified: bool,
    staging_environment: bool,
    artifact_integrity: bool,
    minimum_signoffs: int,
    approval_signoffs: int,
    rejection_signoffs: int = 0,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    scenario_rows = list(scenarios)
    check_rows = list(checks)
    for row in scenario_rows:
        if row.severity in {"critical", "required"} and row.status != "passed":
            reasons.append(f"{row.severity} validation not passed: {row.key}")
    for row in check_rows:
        if row.required and row.status not in {"passed", "waived"}:
            reasons.append(f"pilot-readiness check incomplete: {row.key}")
    if not release_approved:
        reasons.append("underlying release run is not approved")
    if not rollback_verified:
        reasons.append("verified rollback point missing")
    if not staging_environment:
        reasons.append("staging environment evidence missing")
    if not artifact_integrity:
        reasons.append("release-candidate artifact integrity missing")
    if rejection_signoffs:
        reasons.append(f"{rejection_signoffs} rejecting validation sign-off(s) recorded")
    if approval_signoffs < max(1, minimum_signoffs):
        reasons.append(f"validation sign-offs {approval_signoffs}/{max(1, minimum_signoffs)}")
    return not reasons, reasons


def evaluate_numeric_thresholds(metrics: dict, thresholds: dict) -> tuple[bool, list[str]]:
    """Safe threshold evaluator; no arbitrary expressions or code execution."""
    reasons: list[str] = []
    for key, limit in dict(thresholds.get("max") or {}).items():
        actual = metrics.get(key)
        if actual is None or float(actual) > float(limit):
            reasons.append(f"{key} exceeds maximum {limit}; actual={actual}")
    for key, limit in dict(thresholds.get("min") or {}).items():
        actual = metrics.get(key)
        if actual is None or float(actual) < float(limit):
            reasons.append(f"{key} below minimum {limit}; actual={actual}")
    for key, expected in dict(thresholds.get("equals") or {}).items():
        if metrics.get(key) != expected:
            reasons.append(f"{key} must equal {expected!r}; actual={metrics.get(key)!r}")
    return not reasons, reasons


def build_candidate_manifest(
    *,
    candidate_version: str,
    app_version: str,
    database_revision: str | None,
    artifact_sha256: str | None,
    campaign_hash: str | None,
    release_hash: str | None,
    validation_summary: dict,
    datasets: Iterable[dict],
) -> dict:
    dataset_rows = sorted(
        ({"kind": str(row.get("kind")), "name": str(row.get("name")), "sha256": str(row.get("sha256"))} for row in datasets),
        key=lambda row: (row["kind"], row["name"]),
    )
    payload = {
        "candidate_version": candidate_version,
        "app_version": app_version,
        "database_revision": database_revision,
        "artifact_sha256": artifact_sha256,
        "campaign_hash": campaign_hash,
        "release_hash": release_hash,
        "validation": validation_summary,
        "datasets": dataset_rows,
    }
    return {**payload, "snapshot_hash": canonical_hash(payload)}


def synthetic_fixture_manifest(*, seed: int, documents: int, pages_per_document: int, languages: list[str]) -> dict:
    payload = {
        "seed": int(seed),
        "documents": max(0, int(documents)),
        "pages_per_document": max(1, int(pages_per_document)),
        "languages": sorted({str(item) for item in languages}),
    }
    payload["pages"] = payload["documents"] * payload["pages_per_document"]
    payload["sha256"] = canonical_hash(payload)
    return payload
