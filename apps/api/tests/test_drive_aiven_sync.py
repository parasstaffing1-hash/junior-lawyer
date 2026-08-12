from datetime import datetime, timezone

import pytest

from scripts.sync_google_drive_to_aiven import (
    _database_dsn,
    _is_unchanged,
    _parse_service_account,
)


def test_parse_service_account_accepts_raw_json() -> None:
    parsed = _parse_service_account(
        '{"client_email":"sync@example.iam.gserviceaccount.com","private_key":"key"}'
    )
    assert parsed["client_email"] == "sync@example.iam.gserviceaccount.com"


def test_database_dsn_accepts_sqlalchemy_asyncpg_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AIVEN_DATABASE_URL",
        "postgresql+asyncpg://user:password@example.aivencloud.com:12345/defaultdb?sslmode=require",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert _database_dsn().startswith("postgresql://")
    assert "+asyncpg" not in _database_dsn()


def test_is_unchanged_prefers_checksum_and_modified_time() -> None:
    modified = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
    existing = {"modified_time": modified, "md5_checksum": "abc"}
    item = {
        "modifiedTime": "2026-08-12T12:00:00Z",
        "md5Checksum": "abc",
    }
    assert _is_unchanged(existing, item) is True


def test_changed_checksum_is_not_unchanged() -> None:
    modified = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
    existing = {"modified_time": modified, "md5_checksum": "abc"}
    item = {
        "modifiedTime": "2026-08-12T12:00:00Z",
        "md5Checksum": "different",
    }
    assert _is_unchanged(existing, item) is False
