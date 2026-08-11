from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.services.language.normalizer import normalize_legal_text
from app.services.research.ranking import bm25_scores, expand_query, make_snippet, tokenize


@dataclass(frozen=True, slots=True)
class RankedKnowledge:
    index: int
    lexical_score: float
    quality_score: float
    final_score: float
    snippet: str


def canonical_asset_payload(*, title: str, body_en: str | None, body_hi: str | None, summary: str | None) -> dict:
    return {
        "title": " ".join(title.split()),
        "body_en": " ".join((body_en or "").split()),
        "body_hi": " ".join((body_hi or "").split()),
        "summary": " ".join((summary or "").split()),
    }


def content_hash(*, title: str, body_en: str | None, body_hi: str | None, summary: str | None) -> str:
    payload = canonical_asset_payload(title=title, body_en=body_en, body_hi=body_hi, summary=summary)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_search_text(*, title: str, body_en: str | None, body_hi: str | None, summary: str | None, tags: list[str] | None = None, practice_area: str | None = None, matter_type: str | None = None) -> str:
    fields = [title, summary or "", body_en or "", body_hi or "", practice_area or "", matter_type or ""]
    fields.extend(tags or [])
    return normalize_legal_text(" ".join(fields))


def rank_knowledge(query: str, documents: list[str], qualities: list[float] | None = None, *, limit: int = 25) -> tuple[str, list[RankedKnowledge]]:
    normalized_query, terms = expand_query(query)
    if not terms:
        terms = tokenize(query)
    lexical = bm25_scores(terms, documents)
    qualities = qualities or [0.5] * len(documents)
    results: list[RankedKnowledge] = []
    for idx, text in enumerate(documents):
        q = max(0.0, min(float(qualities[idx] if idx < len(qualities) else 0.5), 1.0))
        # Retrieval remains mostly lexical; quality is a conservative tie-breaker.
        final = min(1.0, lexical[idx] * 0.88 + q * 0.12)
        if lexical[idx] <= 0:
            continue
        results.append(RankedKnowledge(idx, lexical[idx], q, final, make_snippet(text, terms)))
    results.sort(key=lambda item: (item.final_score, item.lexical_score, item.quality_score), reverse=True)
    return normalized_query, results[:limit]
