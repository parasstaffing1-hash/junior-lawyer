from datetime import datetime, timedelta, timezone

from app import models  # noqa: F401
from app.db.base import Base
from app.services.legal_data.engine import (
    allowed_source_host,
    canonical_sha256,
    classify_hash_change,
    is_stale,
    release_manifest_hash,
)


def test_batch26_tables_registered():
    expected = {
        "legal_data_feeds", "legal_data_ingestion_runs", "legal_data_ingestion_items",
        "legal_data_source_snapshots", "legal_data_integrity_checks", "statute_amendment_events",
        "jurisdiction_packs", "jurisdiction_pack_releases", "jurisdiction_pack_sources",
        "legal_data_alerts", "legal_corpus_checkpoints",
    }
    assert expected <= set(Base.metadata.tables)
    assert len(Base.metadata.tables) == 255


def test_canonical_hash_ignores_dict_key_order():
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_authoritative_host_validation_is_https_and_allowlisted():
    assert allowed_source_host("https://www.indiacode.nic.in/abc", ["indiacode.nic.in"])[0] is True
    assert allowed_source_host("https://sub.judgments.ecourts.gov.in/a", ["judgments.ecourts.gov.in"])[0] is True
    assert allowed_source_host("http://indiacode.nic.in/a", ["indiacode.nic.in"])[0] is False
    assert allowed_source_host("https://indiacode.nic.in.evil.example/a", ["indiacode.nic.in"])[0] is False


def test_stale_feed_is_deterministic():
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    assert is_stale(None, 72, now=now) is True
    assert is_stale(now - timedelta(hours=71), 72, now=now) is False
    assert is_stale(now - timedelta(hours=73), 72, now=now) is True


def test_hash_change_classification():
    assert classify_hash_change(None, "a") == "new"
    assert classify_hash_change("A", "a") == "unchanged"
    assert classify_hash_change("a", "b") == "updated"


def test_pack_manifest_hash_is_source_order_independent():
    left = [
        {"source_id": "2", "feed_id": "b", "required": True, "maximum_age_hours": 24},
        {"source_id": "1", "feed_id": "a", "required": True, "maximum_age_hours": 72},
    ]
    right = list(reversed(left))
    assert release_manifest_hash(pack_key="india", version="1.0", effective_from=None, effective_to=None, sources=left) == release_manifest_hash(pack_key="india", version="1.0", effective_from=None, effective_to=None, sources=right)


def test_source_host_allows_subdomain_but_not_suffix_attack():
    assert allowed_source_host("https://sub.indiacode.nic.in/path", ["indiacode.nic.in"])[0] is True
    assert allowed_source_host("https://indiacode.nic.in.evil.example/path", ["indiacode.nic.in"])[0] is False


def test_filesystem_drop_path_must_stay_under_configured_root(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.services.legal_data import service

    monkeypatch.setattr(service.settings, "legal_data_import_root", tmp_path)
    good = SimpleNamespace(import_path="india-code/central")
    assert service._safe_import_directory(good) == (tmp_path / "india-code" / "central").resolve()

    bad = SimpleNamespace(import_path="../../escape")
    try:
        service._safe_import_directory(bad)
    except RuntimeError as exc:
        assert "escapes" in str(exc)
    else:
        raise AssertionError("path traversal should be rejected")
