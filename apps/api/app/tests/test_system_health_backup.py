from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import settings
from app.services.system_health import service


def test_sqlite_backup_and_isolated_verification(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE matters (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        conn.execute("INSERT INTO matters(title) VALUES ('राम कुमार v State'), ('ABC v XYZ')")
        conn.commit()

    target = tmp_path / "backup" / "database.sqlite3"
    monkeypatch.setattr(settings, "database_url", f"sqlite+pysqlite:///{source}")
    service._backup_sqlite(target)

    assert target.exists()
    ok, details = service._verify_database_artifact(target)
    assert ok is True
    assert details["quick_check"] == "ok"
    assert details["table_count"] >= 1

    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT count(*) FROM matters").fetchone()[0] == 2


def test_document_backup_zip_and_verification(tmp_path: Path, monkeypatch):
    storage = tmp_path / "documents"
    storage.mkdir()
    (storage / "english.txt").write_text("Affidavit and evidence", encoding="utf-8")
    (storage / "hindi.txt").write_text("शपथपत्र और साक्ष्य", encoding="utf-8")
    staging = storage / ".staging"
    staging.mkdir()
    (staging / "temporary.txt").write_text("skip", encoding="utf-8")

    monkeypatch.setattr(settings, "storage_root", storage)
    out = tmp_path / "backup-files"
    out.mkdir()
    archive, count = service._backup_documents(out)

    assert archive.exists()
    assert count == 2
    ok, details = service._verify_documents_artifact(archive)
    assert ok is True
    assert details["file_count"] == 2


def test_s3_document_objects_are_included_in_backup(tmp_path: Path, monkeypatch):
    from app.services.documents import storage as document_storage

    class Paginator:
        def paginate(self, **_kwargs):
            return [{"Contents": [{"Key": "matter/doc/order.txt"}, {"Key": "matter/doc/आदेश.txt"}]}]

    class FakeS3:
        payloads = {
            "matter/doc/order.txt": b"Order and evidence",
            "matter/doc/आदेश.txt": "आदेश और साक्ष्य".encode("utf-8"),
        }
        def get_paginator(self, name):
            assert name == "list_objects_v2"
            return Paginator()
        def download_fileobj(self, bucket, key, target):
            assert bucket == "legal-documents"
            target.write(self.payloads[key])

    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "storage_s3_bucket", "legal-documents")
    monkeypatch.setattr(settings, "storage_root", tmp_path / "generated")
    monkeypatch.setattr(document_storage, "_s3_client", lambda: FakeS3())
    out = tmp_path / "backup-s3"; out.mkdir()
    archive, count = service._backup_documents(out)
    assert count == 2
    ok, details = service._verify_documents_artifact(archive)
    assert ok is True
    assert details["file_count"] == 2
