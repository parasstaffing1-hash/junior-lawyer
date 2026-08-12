from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

import asyncpg
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

LOGGER = logging.getLogger("drive_aiven_sync")
DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_MIME_PREFIX = "application/vnd.google-apps."
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DEFAULT_FOLDER_NAME = "junior-lawyer-data"
DEFAULT_MAX_CONTENT_MB = 25

GOOGLE_EXPORTS: dict[str, tuple[str, str]] = {
    "application/vnd.google-apps.document": ("text/plain", ".txt"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.presentation": ("text/plain", ".txt"),
}
TEXT_MIME_TYPES = {
    "application/json",
    "application/ld+json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/csv",
    "text/csv",
    "text/markdown",
    "text/plain",
    "text/xml",
    "text/yaml",
}


@dataclass(slots=True)
class SyncStats:
    discovered: int = 0
    inserted_or_updated: int = 0
    unchanged: int = 0
    content_stored: int = 0
    metadata_only: int = 0
    errors: int = 0
    soft_deleted: int = 0


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _parse_service_account(raw: str) -> dict[str, Any]:
    value = raw.strip()
    if not value:
        raise ValueError("Google service-account credentials are empty")
    if value.startswith("{"):
        parsed = json.loads(value)
    else:
        try:
            parsed = json.loads(base64.b64decode(value).decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                "Google credentials must be raw service-account JSON or base64-encoded JSON"
            ) from exc
    if not isinstance(parsed, dict) or not parsed.get("client_email") or not parsed.get("private_key"):
        raise ValueError("Google service-account JSON is missing client_email/private_key")
    return parsed


def _database_dsn() -> str:
    raw = (os.getenv("AIVEN_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("AIVEN_DATABASE_URL (or DATABASE_URL) is required")
    # The application normally uses SQLAlchemy's postgresql+asyncpg scheme; asyncpg expects postgres/postgresql.
    raw = raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    raw = raw.replace("postgres+asyncpg://", "postgresql://", 1)
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if not raw.startswith("postgresql://"):
        raise RuntimeError("Drive sync requires a PostgreSQL/Aiven connection URL")
    return raw


def _credentials_raw() -> str:
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("STORAGE_GDRIVE_CREDENTIALS_JSON")
    if not raw:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON (or STORAGE_GDRIVE_CREDENTIALS_JSON) is required"
        )
    return raw


def _build_drive_service():
    info = _parse_service_account(_credentials_raw())
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=[DRIVE_READONLY_SCOPE],
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _resolve_root_folder(service, explicit_id: str | None, folder_name: str) -> dict[str, Any]:
    if explicit_id:
        folder = (
            service.files()
            .get(
                fileId=explicit_id,
                fields="id,name,mimeType,trashed,webViewLink",
                supportsAllDrives=True,
            )
            .execute(num_retries=5)
        )
        if folder.get("trashed") or folder.get("mimeType") != DRIVE_FOLDER_MIME:
            raise RuntimeError(f"GOOGLE_DRIVE_FOLDER_ID {explicit_id!r} is not an active Drive folder")
        return folder

    escaped = _escape_drive_query(folder_name)
    response = (
        service.files()
        .list(
            q=(
                f"name = '{escaped}' and mimeType = '{DRIVE_FOLDER_MIME}' and trashed = false"
            ),
            fields="files(id,name,mimeType,webViewLink)",
            pageSize=100,
            spaces="drive",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute(num_retries=5)
    )
    folders = response.get("files", [])
    if not folders:
        raise RuntimeError(
            f"No accessible Google Drive folder named {folder_name!r}. "
            "Share it with the service-account email or set GOOGLE_DRIVE_FOLDER_ID."
        )
    if len(folders) > 1:
        ids = ", ".join(str(item.get("id")) for item in folders)
        raise RuntimeError(
            f"Multiple Drive folders are named {folder_name!r} ({ids}). Set GOOGLE_DRIVE_FOLDER_ID."
        )
    return folders[0]


def _list_children(service, folder_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        response = (
            service.files()
            .list(
                q=f"'{_escape_drive_query(folder_id)}' in parents and trashed = false",
                fields=(
                    "nextPageToken,files("
                    "id,name,mimeType,parents,modifiedTime,md5Checksum,size,webViewLink,"
                    "description,createdTime,owners(displayName,emailAddress))"
                ),
                pageSize=1000,
                pageToken=page_token,
                spaces="drive",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute(num_retries=5)
        )
        result.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return result


def _walk_files(service, root_folder_id: str, root_name: str):
    queue: list[tuple[str, PurePosixPath]] = [(root_folder_id, PurePosixPath(root_name))]
    while queue:
        folder_id, folder_path = queue.pop(0)
        for item in _list_children(service, folder_id):
            item_path = folder_path / str(item.get("name") or item["id"])
            if item.get("mimeType") == DRIVE_FOLDER_MIME:
                queue.append((item["id"], item_path))
            else:
                yield item, item_path.as_posix()


def _download_request(request, *, max_bytes: int) -> bytes:
    target = io.BytesIO()
    downloader = MediaIoBaseDownload(target, request, chunksize=1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk(num_retries=5)
        if target.tell() > max_bytes:
            raise ValueError(f"content exceeds configured {max_bytes} byte extraction limit")
    return target.getvalue()


def _download_file(service, item: dict[str, Any], *, max_bytes: int) -> tuple[bytes | None, str]:
    mime_type = str(item.get("mimeType") or "application/octet-stream")
    declared_size = int(item.get("size") or 0)
    if declared_size and declared_size > max_bytes:
        return None, "too_large"

    if mime_type.startswith(GOOGLE_MIME_PREFIX):
        export = GOOGLE_EXPORTS.get(mime_type)
        if not export:
            return None, "unsupported_google_type"
        export_mime, _ = export
        try:
            request = service.files().export_media(fileId=item["id"], mimeType=export_mime)
            return _download_request(request, max_bytes=max_bytes), "downloaded"
        except HttpError as exc:
            LOGGER.warning("Google export unavailable for %s (%s): %s", item["id"], mime_type, exc)
            return None, "export_unavailable"

    request = service.files().get_media(fileId=item["id"], supportsAllDrives=True)
    return _download_request(request, max_bytes=max_bytes), "downloaded"


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding).replace("\x00", "")
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace").replace("\x00", "")


def _extract_text(content: bytes, mime_type: str, name: str) -> tuple[str | None, str]:
    lowered = name.casefold()
    if mime_type.startswith("text/") or mime_type in TEXT_MIME_TYPES or lowered.endswith(
        (".txt", ".md", ".csv", ".json", ".jsonl", ".xml", ".yaml", ".yml", ".html", ".htm")
    ):
        return _decode_text(content), "stored"

    if mime_type == "application/pdf" or lowered.endswith(".pdf"):
        try:
            import fitz

            with fitz.open(stream=content, filetype="pdf") as document:
                return "\n\n".join(page.get_text("text") for page in document), "stored"
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("PDF text extraction failed for %s: %s", name, exc)
            return None, "extract_error"

    if (
        mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or lowered.endswith(".docx")
    ):
        try:
            from docx import Document

            document = Document(io.BytesIO(content))
            return "\n".join(paragraph.text for paragraph in document.paragraphs), "stored"
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("DOCX text extraction failed for %s: %s", name, exc)
            return None, "extract_error"

    return None, "unsupported_content_type"


def _parse_drive_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS drive_sync_runs (
    id UUID PRIMARY KEY,
    root_folder_id TEXT NOT NULL,
    root_folder_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    discovered INTEGER NOT NULL DEFAULT 0,
    inserted_or_updated INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    content_stored INTEGER NOT NULL DEFAULT 0,
    metadata_only INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    soft_deleted INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS drive_sync_files (
    drive_file_id TEXT PRIMARY KEY,
    root_folder_id TEXT NOT NULL,
    name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    drive_path TEXT NOT NULL,
    web_view_link TEXT,
    modified_time TIMESTAMPTZ,
    md5_checksum TEXT,
    size_bytes BIGINT,
    content_sha256 TEXT,
    content_text TEXT,
    content_state TEXT NOT NULL DEFAULT 'metadata_only',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_drive_sync_files_root ON drive_sync_files(root_folder_id);
CREATE INDEX IF NOT EXISTS ix_drive_sync_files_path ON drive_sync_files(root_folder_id, drive_path);
CREATE INDEX IF NOT EXISTS ix_drive_sync_files_modified ON drive_sync_files(modified_time DESC);
CREATE INDEX IF NOT EXISTS ix_drive_sync_files_content_fts
ON drive_sync_files USING GIN (to_tsvector('simple', COALESCE(content_text, '')));
"""


async def _ensure_schema(connection: asyncpg.Connection) -> None:
    await connection.execute(SCHEMA_SQL)


async def _existing_file(connection: asyncpg.Connection, file_id: str):
    return await connection.fetchrow(
        "SELECT modified_time, md5_checksum FROM drive_sync_files WHERE drive_file_id = $1",
        file_id,
    )


def _is_unchanged(existing, item: dict[str, Any]) -> bool:
    if not existing:
        return False
    incoming_modified = _parse_drive_time(item.get("modifiedTime"))
    stored_modified = existing["modified_time"]
    incoming_md5 = item.get("md5Checksum")
    stored_md5 = existing["md5_checksum"]
    if incoming_md5 and stored_md5:
        return incoming_md5 == stored_md5 and incoming_modified == stored_modified
    return incoming_modified == stored_modified


async def _touch_unchanged(
    connection: asyncpg.Connection,
    *,
    root_folder_id: str,
    item: dict[str, Any],
    drive_path: str,
    seen_at: datetime,
) -> None:
    metadata_json = json.dumps(
        {
            "description": item.get("description"),
            "createdTime": item.get("createdTime"),
            "owners": item.get("owners") or [],
        },
        ensure_ascii=False,
    )
    await connection.execute(
        """
        UPDATE drive_sync_files
        SET root_folder_id = $2, name = $3, mime_type = $4, drive_path = $5,
            web_view_link = $6, size_bytes = $7, metadata = $8::jsonb,
            last_seen_at = $9, deleted_at = NULL
        WHERE drive_file_id = $1
        """,
        item["id"],
        root_folder_id,
        str(item.get("name") or item["id"]),
        str(item.get("mimeType") or "application/octet-stream"),
        drive_path,
        item.get("webViewLink"),
        int(item.get("size") or 0) or None,
        metadata_json,
        seen_at,
    )


async def _upsert_changed(
    connection: asyncpg.Connection,
    *,
    root_folder_id: str,
    item: dict[str, Any],
    drive_path: str,
    content_sha256: str | None,
    content_text: str | None,
    content_state: str,
    seen_at: datetime,
) -> None:
    metadata_json = json.dumps(
        {
            "description": item.get("description"),
            "createdTime": item.get("createdTime"),
            "owners": item.get("owners") or [],
        },
        ensure_ascii=False,
    )
    await connection.execute(
        """
        INSERT INTO drive_sync_files (
            drive_file_id, root_folder_id, name, mime_type, drive_path, web_view_link,
            modified_time, md5_checksum, size_bytes, content_sha256, content_text,
            content_state, metadata, first_seen_at, last_seen_at, synced_at, deleted_at
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,$14,$14,$14,NULL
        )
        ON CONFLICT (drive_file_id) DO UPDATE SET
            root_folder_id = EXCLUDED.root_folder_id,
            name = EXCLUDED.name,
            mime_type = EXCLUDED.mime_type,
            drive_path = EXCLUDED.drive_path,
            web_view_link = EXCLUDED.web_view_link,
            modified_time = EXCLUDED.modified_time,
            md5_checksum = EXCLUDED.md5_checksum,
            size_bytes = EXCLUDED.size_bytes,
            content_sha256 = EXCLUDED.content_sha256,
            content_text = EXCLUDED.content_text,
            content_state = EXCLUDED.content_state,
            metadata = EXCLUDED.metadata,
            last_seen_at = EXCLUDED.last_seen_at,
            synced_at = EXCLUDED.synced_at,
            deleted_at = NULL
        """,
        item["id"],
        root_folder_id,
        str(item.get("name") or item["id"]),
        str(item.get("mimeType") or "application/octet-stream"),
        drive_path,
        item.get("webViewLink"),
        _parse_drive_time(item.get("modifiedTime")),
        item.get("md5Checksum"),
        int(item.get("size") or 0) or None,
        content_sha256,
        content_text,
        content_state,
        metadata_json,
        seen_at,
    )


async def sync(args: argparse.Namespace) -> SyncStats:
    service = _build_drive_service()
    root = _resolve_root_folder(service, args.folder_id, args.folder_name)
    root_id = str(root["id"])
    root_name = str(root.get("name") or args.folder_name)
    LOGGER.info("Drive root resolved: %s (%s)", root_name, root_id)

    max_bytes = args.max_content_mb * 1024 * 1024
    store_content = not args.metadata_only
    connection = await asyncpg.connect(_database_dsn(), command_timeout=120)
    run_id = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    stats = SyncStats()

    try:
        await _ensure_schema(connection)
        await connection.execute(
            """
            INSERT INTO drive_sync_runs (id, root_folder_id, root_folder_name, started_at, status)
            VALUES ($1,$2,$3,$4,'running')
            """,
            run_id,
            root_id,
            root_name,
            started_at,
        )

        for item, drive_path in _walk_files(service, root_id, root_name):
            stats.discovered += 1
            try:
                existing = await _existing_file(connection, item["id"])
                seen_at = datetime.now(timezone.utc)
                if _is_unchanged(existing, item):
                    await _touch_unchanged(
                        connection,
                        root_folder_id=root_id,
                        item=item,
                        drive_path=drive_path,
                        seen_at=seen_at,
                    )
                    stats.unchanged += 1
                    continue

                content_sha256: str | None = None
                content_text: str | None = None
                content_state = "metadata_only"
                if store_content:
                    raw_content, download_state = _download_file(
                        service,
                        item,
                        max_bytes=max_bytes,
                    )
                    if raw_content is not None:
                        content_sha256 = hashlib.sha256(raw_content).hexdigest()
                        content_text, content_state = _extract_text(
                            raw_content,
                            str(item.get("mimeType") or ""),
                            str(item.get("name") or item["id"]),
                        )
                        if content_text is not None:
                            stats.content_stored += 1
                        else:
                            stats.metadata_only += 1
                    else:
                        content_state = download_state
                        stats.metadata_only += 1
                else:
                    content_state = "metadata_only_by_config"
                    stats.metadata_only += 1

                await _upsert_changed(
                    connection,
                    root_folder_id=root_id,
                    item=item,
                    drive_path=drive_path,
                    content_sha256=content_sha256,
                    content_text=content_text,
                    content_state=content_state,
                    seen_at=seen_at,
                )
                stats.inserted_or_updated += 1
            except Exception:  # noqa: BLE001
                stats.errors += 1
                LOGGER.exception("Failed to sync Drive file %s (%s)", drive_path, item.get("id"))
                if args.fail_fast:
                    raise

        # Only mark missing rows after a complete traversal. A failed traversal never mass-deletes rows.
        deleted = await connection.fetchval(
            """
            WITH changed AS (
                UPDATE drive_sync_files
                SET deleted_at = NOW()
                WHERE root_folder_id = $1
                  AND deleted_at IS NULL
                  AND last_seen_at < $2
                RETURNING 1
            )
            SELECT COUNT(*) FROM changed
            """,
            root_id,
            started_at,
        )
        stats.soft_deleted = int(deleted or 0)

        await connection.execute(
            """
            UPDATE drive_sync_runs
            SET completed_at = NOW(), status = $2, discovered = $3,
                inserted_or_updated = $4, unchanged = $5, content_stored = $6,
                metadata_only = $7, errors = $8, soft_deleted = $9
            WHERE id = $1
            """,
            run_id,
            "completed_with_errors" if stats.errors else "completed",
            stats.discovered,
            stats.inserted_or_updated,
            stats.unchanged,
            stats.content_stored,
            stats.metadata_only,
            stats.errors,
            stats.soft_deleted,
        )
    except Exception as exc:
        try:
            await connection.execute(
                """
                UPDATE drive_sync_runs
                SET completed_at = NOW(), status = 'failed', error_message = $2,
                    discovered = $3, inserted_or_updated = $4, unchanged = $5,
                    content_stored = $6, metadata_only = $7, errors = $8
                WHERE id = $1
                """,
                run_id,
                str(exc)[:4000],
                stats.discovered,
                stats.inserted_or_updated,
                stats.unchanged,
                stats.content_stored,
                stats.metadata_only,
                stats.errors + 1,
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("Could not persist failed sync-run status")
        raise
    finally:
        await connection.close()

    return stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Incrementally sync a Google Drive folder into an Aiven PostgreSQL catalog."
    )
    parser.add_argument(
        "--folder-id",
        default=os.getenv("GOOGLE_DRIVE_FOLDER_ID") or os.getenv("STORAGE_GDRIVE_ROOT_FOLDER_ID"),
        help="Exact Drive root folder ID. If omitted, the folder is resolved by name.",
    )
    parser.add_argument(
        "--folder-name",
        default=os.getenv("GOOGLE_DRIVE_FOLDER_NAME", DEFAULT_FOLDER_NAME),
        help=f"Drive root folder name (default: {DEFAULT_FOLDER_NAME}).",
    )
    parser.add_argument(
        "--max-content-mb",
        type=int,
        default=int(os.getenv("DRIVE_SYNC_CONTENT_MAX_MB", str(DEFAULT_MAX_CONTENT_MB))),
        help="Maximum bytes downloaded/extracted per file; larger files remain metadata-only.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        default=not _env_bool("DRIVE_SYNC_STORE_CONTENT", True),
        help="Only catalog metadata; do not download or extract file contents.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=_env_bool("DRIVE_SYNC_FAIL_FAST", False),
        help="Stop on the first individual file failure.",
    )
    return parser


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = _build_parser().parse_args()
    if args.max_content_mb <= 0:
        raise SystemExit("--max-content-mb must be greater than zero")
    try:
        stats = asyncio.run(sync(args))
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Drive → Aiven sync failed: %s", exc)
        return 1
    LOGGER.info("Drive → Aiven sync complete: %s", stats)
    return 0 if stats.errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
