from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from app.models.operations import ChangeSeverity, CourtChangeType


@dataclass(frozen=True, slots=True)
class DetectedChange:
    change_type: CourtChangeType
    severity: ChangeSeverity
    summary: str
    old_value: str | None
    new_value: str | None


def stable_snapshot_hash(payload: dict) -> str:
    clean = {key: payload.get(key) for key in (
        "case_status", "stage", "next_hearing_date", "judge_or_bench", "order_count",
        "latest_order_date", "latest_order_reference",
    )}
    raw = json.dumps(clean, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _s(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value).strip() or None


def detect_snapshot_changes(previous: dict | None, current: dict) -> list[DetectedChange]:
    if not previous:
        return []
    changes: list[DetectedChange] = []
    old_orders = int(previous.get("order_count") or 0)
    new_orders = int(current.get("order_count") or 0)
    old_order_date, new_order_date = _s(previous.get("latest_order_date")), _s(current.get("latest_order_date"))
    old_order_ref, new_order_ref = _s(previous.get("latest_order_reference")), _s(current.get("latest_order_reference"))
    if new_orders > old_orders or (new_order_date and new_order_date != old_order_date) or (new_order_ref and new_order_ref != old_order_ref):
        changes.append(DetectedChange(
            CourtChangeType.NEW_ORDER, ChangeSeverity.HIGH, "New court order/proceeding detected",
            old_order_ref or old_order_date or str(old_orders), new_order_ref or new_order_date or str(new_orders),
        ))

    old_hearing, new_hearing = _s(previous.get("next_hearing_date")), _s(current.get("next_hearing_date"))
    if old_hearing != new_hearing and (old_hearing or new_hearing):
        changes.append(DetectedChange(
            CourtChangeType.HEARING_DATE_CHANGED, ChangeSeverity.HIGH, "Next hearing date changed",
            old_hearing, new_hearing,
        ))

    pairs = (
        ("case_status", CourtChangeType.CASE_STATUS_CHANGED, ChangeSeverity.MEDIUM, "Case status changed"),
        ("stage", CourtChangeType.STAGE_CHANGED, ChangeSeverity.MEDIUM, "Case stage changed"),
        ("judge_or_bench", CourtChangeType.JUDGE_CHANGED, ChangeSeverity.INFO, "Judge/bench changed"),
    )
    for field, kind, severity, summary in pairs:
        old, new = _s(previous.get(field)), _s(current.get(field))
        if old != new and (old or new):
            changes.append(DetectedChange(kind, severity, summary, old, new))
    return changes
