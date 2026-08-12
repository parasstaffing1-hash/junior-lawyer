"""Ingest a bare-acts dataset from Google Drive into the legal corpus.

The dataset is a JSON array of acts shaped like `sample_bare_acts.json`:

    [{"id": "bns_2023", "title": "...", "year": 2023, "type": "Central",
      "title_hi": "...",                                  # optional
      "sections": [{"section_number": "302", "title": "...", "text": "...",
                    "heading_hi": "...", "text_hi": "...",  # optional
                    "simplified_explanation": "..."}]}]

This script only *translates* the dataset; the actual write goes through
`app.services.research.importer.import_statute`, which is version-aware,
computes SHA-256 provenance hashes, applies the canonical text normalizer used
by search, and upserts instead of skipping records that already exist.

Drive access uses the same service-account credentials as document storage:
`STORAGE_GDRIVE_CREDENTIALS_JSON` (base64-encoded service-account JSON) and
`STORAGE_GDRIVE_ROOT_FOLDER_ID`. Share the Drive file with the service account's
address, not with a personal account.

Usage:
    # Inspect and size the dataset. Writes nothing. This is the default.
    python -m scripts.ingest_bare_acts_from_drive <drive_file_id>

    # Load a small slice first to sanity-check the mapping.
    python -m scripts.ingest_bare_acts_from_drive <drive_file_id> --commit --limit 5

    # Full load.
    python -m scripts.ingest_bare_acts_from_drive <drive_file_id> --commit
"""
from __future__ import annotations

import argparse
import asyncio
import json
from io import BytesIO
from typing import Any

from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.legal_corpus import AccessMode, LegalSource, LegalSourceKind
from app.schemas.research import StatuteImportRequest, StatuteImportSection
from app.services.documents.storage import _gdrive_service
from app.services.research import importer

# A Drive dataset is not an authoritative official download, so it is registered
# as a non-official manual source. Search and remedy verification treat official
# and unofficial provenance differently; do not relabel this as official.
DRIVE_SOURCE_CODE = "drive_dataset"


def download_dataset(file_id: str) -> list[dict[str, Any]]:
    service = _gdrive_service()
    request = service.files().get_media(fileId=file_id)
    buffer = BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"  download {int(status.progress() * 100)}%")
    buffer.seek(0)
    data = json.load(buffer)
    if not isinstance(data, list):
        raise SystemExit("Dataset must be a JSON array of acts")
    return data


async def ensure_drive_source(db: AsyncSession) -> LegalSource:
    source = await db.scalar(select(LegalSource).where(LegalSource.code == DRIVE_SOURCE_CODE))
    if source:
        return source
    source = LegalSource(
        code=DRIVE_SOURCE_CODE,
        name="Bare Acts dataset (Google Drive)",
        kind=LegalSourceKind.MANUAL,
        jurisdiction="India",
        official=False,
        access_mode=AccessMode.MANUAL_IMPORT,
        enabled=True,
        notes="Curated dataset imported from Google Drive. Not an official download; verify against India Code before relying on it.",
        metadata_json={},
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


def build_request(act: dict[str, Any]) -> StatuteImportRequest | None:
    """Translate one dataset act into an import request, or None if unusable."""
    external_id = str(act.get("id") or "").strip()
    if not external_id:
        # Generating a random id here would break idempotency: every re-run
        # would insert a duplicate act instead of updating the existing one.
        print(f"  ! skipped (no stable 'id'): {act.get('title', '<untitled>')}")
        return None

    sections: list[StatuteImportSection] = []
    for position, raw in enumerate(act.get("sections") or []):
        number = str(raw.get("section_number") or "").strip() or str(position + 1)
        metadata = {
            key: raw[key]
            for key in ("simplified_explanation", "audio_url")
            if raw.get(key) is not None
        }
        sections.append(
            StatuteImportSection(
                section_number=number,
                heading_en=raw.get("title"),
                heading_hi=raw.get("title_hi") or raw.get("heading_hi"),
                text_en=raw.get("text"),
                text_hi=raw.get("text_hi"),
                metadata=metadata,
            )
        )

    year = act.get("year")
    act_type = act.get("type")
    return StatuteImportRequest(
        source_code=DRIVE_SOURCE_CODE,
        external_id=external_id,
        title_en=act.get("title") or "Untitled act",
        title_hi=act.get("title_hi"),
        # `year` is nullable in the model. Defaulting an unknown year to a
        # placeholder would put invented data into a legal corpus.
        act_year=int(year) if isinstance(year, int) or str(year or "").isdigit() else None,
        # `jurisdiction` is a place, and search filters it as one. The dataset's
        # "type" field is Central/State classification, which belongs in metadata.
        jurisdiction="India",
        state=act.get("state"),
        metadata={"act_type": act_type} if act_type else {},
        sections=sections,
    )


def summarize(requests: list[StatuteImportRequest]) -> None:
    section_count = sum(len(r.sections) for r in requests)
    text_bytes = sum(
        len((s.text_en or "").encode("utf-8")) + len((s.text_hi or "").encode("utf-8"))
        for r in requests
        for s in r.sections
    )
    hindi_sections = sum(1 for r in requests for s in r.sections if s.text_hi)
    print(f"\n  acts:             {len(requests)}")
    print(f"  sections:         {section_count}")
    print(f"  sections w/ Hindi: {hindi_sections}")
    print(f"  raw section text: {text_bytes / 1_048_576:.1f} MiB")
    print(
        "  note: stored size is larger than raw text — normalized_text roughly "
        "doubles it, before indexes."
    )


async def run(file_id: str, *, commit: bool, limit: int | None) -> None:
    print(f"Downloading dataset {file_id} from Google Drive...")
    data = download_dataset(file_id)
    print(f"Loaded {len(data)} acts.")

    if limit is not None:
        data = data[:limit]
        print(f"Limited to first {len(data)} acts.")

    requests = [request for act in data if (request := build_request(act)) is not None]
    summarize(requests)

    if not commit:
        print("\nDry run — nothing was written. Re-run with --commit to import.")
        return

    async with AsyncSessionLocal() as db:
        await ensure_drive_source(db)
        for index, request in enumerate(requests, start=1):
            statute = await importer.import_statute(db, request)
            print(f"  [{index}/{len(requests)}] {statute.title_en} ({len(request.sections)} sections)")
    print("\nIngestion complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file_id", help="Google Drive file id of the dataset JSON")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually write to the database. Without this the script only reports.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N acts")
    args = parser.parse_args()
    asyncio.run(run(args.file_id, commit=args.commit, limit=args.limit))


if __name__ == "__main__":
    main()
