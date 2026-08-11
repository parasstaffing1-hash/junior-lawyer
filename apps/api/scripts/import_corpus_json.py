"""Import normalized legal corpus JSON without any LLM/API calls.

Usage:
    python scripts/import_corpus_json.py ../../corpus_examples/statute.template.json
    python scripts/import_corpus_json.py /path/to/judgment.json

The JSON must contain `type: statute` or `type: judgment`; the remaining object
must match the corresponding Pydantic import schema exposed by the API.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from app.db.session import AsyncSessionLocal
from app.schemas.research import JudgmentImportRequest, StatuteImportRequest
from app.services.research import importer


async def run(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    record_type = payload.pop("type", None)
    async with AsyncSessionLocal() as db:
        await importer.seed_official_sources(db)
        if record_type == "statute":
            record = await importer.import_statute(db, StatuteImportRequest.model_validate(payload))
            print(f"Imported statute {record.id}: {record.title_en}")
            return
        if record_type == "judgment":
            record = await importer.import_judgment(db, JudgmentImportRequest.model_validate(payload))
            await importer.resolve_citations(db, record.id)
            print(f"Imported judgment {record.id}: {record.case_title}")
            return
    raise SystemExit("JSON field 'type' must be either 'statute' or 'judgment'")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_corpus_json.py /path/to/corpus-record.json")
    asyncio.run(run(Path(sys.argv[1]).expanduser().resolve()))
