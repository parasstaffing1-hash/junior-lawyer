from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.models.system_health import HealthStatus, IncidentSeverity


STATUS_ORDER = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.UNKNOWN: 1,
    HealthStatus.DEGRADED: 2,
    HealthStatus.DOWN: 3,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def canonical_hash(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def overall_status(statuses: Iterable[HealthStatus | str]) -> HealthStatus:
    values: list[HealthStatus] = []
    for value in statuses:
        try:
            values.append(value if isinstance(value, HealthStatus) else HealthStatus(str(value)))
        except ValueError:
            values.append(HealthStatus.UNKNOWN)
    return max(values, key=lambda item: STATUS_ORDER[item], default=HealthStatus.UNKNOWN)


def incident_severity(component_key: str, status: HealthStatus | str) -> IncidentSeverity:
    try:
        normalized = status if isinstance(status, HealthStatus) else HealthStatus(str(status))
    except ValueError:
        normalized = HealthStatus.UNKNOWN
    if normalized == HealthStatus.DOWN and component_key in {"database", "storage"}:
        return IncidentSeverity.CRITICAL
    if normalized == HealthStatus.DOWN:
        return IncidentSeverity.HIGH
    if normalized == HealthStatus.DEGRADED:
        return IncidentSeverity.WARNING
    return IncidentSeverity.INFO


def incident_fingerprint(component_key: str) -> str:
    return canonical_hash({"component": component_key, "kind": "system-health"})


def age_seconds(now: datetime, value: datetime | None) -> int | None:
    normalized = aware(value)
    if normalized is None:
        return None
    return max(0, int((aware(now) - normalized).total_seconds()))


def storage_free_percent(total: int, free: int) -> float:
    if total <= 0:
        return 0.0
    return round((max(0, free) / total) * 100.0, 2)


def safe_filename(value: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    cleaned = "".join(ch if ch in allowed else "-" for ch in value).strip(".-")
    return cleaned or "artifact"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def retention_keep_ids(rows: list[tuple[str, datetime]], *, now: datetime, retention_days: int, max_backups: int) -> set[str]:
    cutoff_seconds = max(1, retention_days) * 86400
    ordered = sorted(rows, key=lambda item: aware(item[1]) or aware(now), reverse=True)
    kept: set[str] = set()
    for index, (row_id, created_at) in enumerate(ordered):
        age = max(0, int((aware(now) - (aware(created_at) or aware(now))).total_seconds()))
        if index < max(1, max_backups) and age <= cutoff_seconds:
            kept.add(row_id)
    return kept


def rpo_status(*, last_backup_at: datetime | None, now: datetime, target_minutes: int) -> tuple[HealthStatus, int | None]:
    age = age_seconds(now, last_backup_at)
    if age is None:
        return HealthStatus.DEGRADED, None
    target = max(1, target_minutes) * 60
    if age <= target:
        return HealthStatus.HEALTHY, age
    if age <= target * 2:
        return HealthStatus.DEGRADED, age
    return HealthStatus.DOWN, age


def restore_verification_status(*, last_verified_at: datetime | None, now: datetime, target_days: int) -> tuple[HealthStatus, int | None]:
    age = age_seconds(now, last_verified_at)
    if age is None:
        return HealthStatus.DEGRADED, None
    target = max(1, target_days) * 86400
    return (HealthStatus.HEALTHY if age <= target else HealthStatus.DEGRADED), age


def rrule_interval_seconds(rule: str | None) -> int | None:
    if not rule:
        return None
    parts: dict[str, str] = {}
    for token in rule.strip().upper().split(";"):
        if "=" in token:
            key, value = token.split("=", 1)
            parts[key.strip()] = value.strip()
    frequency = parts.get("FREQ")
    try:
        interval = max(1, int(parts.get("INTERVAL", "1")))
    except ValueError:
        return None
    seconds = {"HOURLY": 3600, "DAILY": 86400, "WEEKLY": 604800}.get(frequency or "")
    return seconds * interval if seconds else None


def schedule_due(*, last_run_at: datetime | None, rule: str | None, now: datetime) -> bool:
    interval = rrule_interval_seconds(rule)
    if interval is None:
        return False
    age = age_seconds(now, last_run_at)
    return age is None or age >= interval
