from __future__ import annotations

from dataclasses import dataclass

from app.models.search import SearchEntityType
from app.services.language.normalizer import normalize_legal_text
from app.services.research.ranking import bm25_scores, expand_query, make_snippet


TYPE_WEIGHT: dict[SearchEntityType, float] = {
    SearchEntityType.MATTER: 1.00,
    SearchEntityType.CLIENT: 0.98,
    SearchEntityType.DOCUMENT: 0.96,
    SearchEntityType.FACT: 0.95,
    SearchEntityType.EVIDENCE: 0.95,
    SearchEntityType.WITNESS: 0.93,
    SearchEntityType.CONTRACT: 0.92,
    SearchEntityType.DRAFT: 0.92,
    SearchEntityType.DEADLINE: 0.95,
    SearchEntityType.HEARING: 0.95,
    SearchEntityType.TASK: 0.93,
    SearchEntityType.INVOICE: 0.90,
    SearchEntityType.STATUTE: 0.94,
    SearchEntityType.JUDGMENT: 0.96,
    SearchEntityType.PRECEDENT: 0.94,
    SearchEntityType.COMMUNICATION: 0.86,
}


@dataclass(slots=True)
class SearchCandidate:
    entity_type: SearchEntityType
    entity_id: object
    title: str
    subtitle: str | None
    searchable_text: str
    href: str
    badges: list[str]
    matter_id: object | None = None
    client_id: object | None = None
    metadata: dict | None = None


@dataclass(slots=True)
class RankedCandidate:
    candidate: SearchCandidate
    score: float
    snippet: str


def rank_candidates(query: str, candidates: list[SearchCandidate], limit: int = 30) -> tuple[str, list[str], list[RankedCandidate]]:
    normalized, terms = expand_query(query)
    if not terms or not candidates:
        return normalized, terms, []
    docs = [normalize_legal_text(f"{c.title} {c.subtitle or ''} {c.searchable_text}") for c in candidates]
    lexical = bm25_scores(terms, docs)
    normalized_cf = normalized.casefold()
    ranked: list[RankedCandidate] = []
    for idx, candidate in enumerate(candidates):
        if lexical[idx] <= 0:
            continue
        title_norm = normalize_legal_text(candidate.title).casefold()
        exact_title = 1.0 if title_norm == normalized_cf else 0.0
        prefix = 1.0 if normalized_cf and title_norm.startswith(normalized_cf) else 0.0
        type_weight = TYPE_WEIGHT.get(candidate.entity_type, 0.85)
        score = lexical[idx] * 0.78 + type_weight * 0.12 + exact_title * 0.07 + prefix * 0.03
        score = min(1.0, score)
        ranked.append(RankedCandidate(candidate, score, make_snippet(docs[idx], terms, radius=150)))
    ranked.sort(key=lambda item: (item.score, item.candidate.title.casefold()), reverse=True)
    return normalized, terms, ranked[:limit]
