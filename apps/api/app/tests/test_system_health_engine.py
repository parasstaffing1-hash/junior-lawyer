from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models.system_health import HealthStatus, IncidentSeverity
from app.services.system_health.engine import (
    canonical_hash,
    incident_severity,
    overall_status,
    restore_verification_status,
    retention_keep_ids,
    rpo_status,
    safe_filename,
    sha256_file,
    storage_free_percent,
)


def test_overall_status_is_worst_component():
    assert overall_status([HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.DOWN]) == HealthStatus.DOWN
    assert overall_status([HealthStatus.HEALTHY]) == HealthStatus.HEALTHY


def test_database_down_is_critical_incident():
    assert incident_severity("database", HealthStatus.DOWN) == IncidentSeverity.CRITICAL
    assert incident_severity("search_index", HealthStatus.DOWN) == IncidentSeverity.HIGH
    assert incident_severity("ocr", HealthStatus.DEGRADED) == IncidentSeverity.WARNING


def test_hash_is_stable_across_key_order():
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})


def test_rpo_status_changes_with_backup_age():
    now = datetime(2026, 8, 8, 12, tzinfo=timezone.utc)
    assert rpo_status(last_backup_at=now - timedelta(minutes=30), now=now, target_minutes=60)[0] == HealthStatus.HEALTHY
    assert rpo_status(last_backup_at=now - timedelta(minutes=90), now=now, target_minutes=60)[0] == HealthStatus.DEGRADED
    assert rpo_status(last_backup_at=now - timedelta(minutes=180), now=now, target_minutes=60)[0] == HealthStatus.DOWN


def test_restore_verification_age_is_review_signal():
    now = datetime(2026, 8, 8, 12, tzinfo=timezone.utc)
    assert restore_verification_status(last_verified_at=now - timedelta(days=10), now=now, target_days=30)[0] == HealthStatus.HEALTHY
    assert restore_verification_status(last_verified_at=now - timedelta(days=45), now=now, target_days=30)[0] == HealthStatus.DEGRADED


def test_retention_respects_age_and_count():
    now = datetime(2026, 8, 8, 12, tzinfo=timezone.utc)
    rows = [("new", now - timedelta(days=1)), ("mid", now - timedelta(days=5)), ("old", now - timedelta(days=90))]
    assert retention_keep_ids(rows, now=now, retention_days=30, max_backups=2) == {"new", "mid"}


def test_safe_filename_blocks_path_tokens():
    assert ".." not in safe_filename("../client backup")
    assert "/" not in safe_filename("client/backup")


def test_sha256_file_and_storage_percentage(tmp_path: Path):
    path = tmp_path / "x.txt"
    path.write_text("legal", encoding="utf-8")
    assert len(sha256_file(path)) == 64
    assert storage_free_percent(100, 25) == 25.0


def test_simple_rrule_scheduler_supports_hourly_daily_weekly():
    from app.services.system_health.engine import rrule_interval_seconds, schedule_due
    now = datetime(2026, 8, 8, 12, tzinfo=timezone.utc)
    assert rrule_interval_seconds("FREQ=DAILY;INTERVAL=2") == 172800
    assert rrule_interval_seconds("FREQ=MONTHLY") is None
    assert schedule_due(last_run_at=now - timedelta(hours=2), rule="FREQ=HOURLY", now=now)
    assert not schedule_due(last_run_at=now - timedelta(minutes=20), rule="FREQ=HOURLY", now=now)
