from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.models.legal_corpus import CourtLevel
from app.services.language.normalizer import normalize_legal_text


TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u0900-\u097F]+")

# Deterministic bilingual legal query expansion. Keep mappings narrow and auditable.
QUERY_EXPANSIONS: dict[str, set[str]] = {
    "bail": {"bail", "जमानत", "zamanat", "jamanat"},
    "जमानत": {"bail", "जमानत", "zamanat", "jamanat"},
    "notice": {"notice", "नोटिस", "legal notice"},
    "termination": {"termination", "dismissal", "discharge", "समाप्ति", "सेवा समाप्ति"},
    "agreement": {"agreement", "contract", "समझौता", "अनुबंध"},
    "contract": {"agreement", "contract", "समझौता", "अनुबंध"},
    "evidence": {"evidence", "proof", "साक्ष्य", "सबूत"},
    "appeal": {"appeal", "अपील"},
    "judgment": {"judgment", "decision", "निर्णय", "फैसला"},
    "section": {"section", "धारा", "dhara"},
    "petitioner": {"petitioner", "याचिकाकर्ता"},
    "respondent": {"respondent", "प्रतिवादी"},
    "cheque": {"cheque", "check", "चेक"},
    "dishonour": {"dishonour", "bounce", "returned unpaid", "अनादरण", "बाउंस"},
    "limitation": {"limitation", "time bar", "सीमा", "परिसीमा"},
}

COURT_AUTHORITY: dict[CourtLevel, float] = {
    CourtLevel.SUPREME_COURT: 1.0,
    CourtLevel.HIGH_COURT: 0.82,
    CourtLevel.APPELLATE_TRIBUNAL: 0.66,
    CourtLevel.TRIBUNAL: 0.56,
    CourtLevel.DISTRICT_COURT: 0.38,
    CourtLevel.OTHER: 0.30,
}


@dataclass(frozen=True, slots=True)
class RankedText:
    lexical: float
    language: float
    final: float


def tokenize(text: str) -> list[str]:
    normalized = normalize_legal_text(text).casefold()
    return [token for token in TOKEN_RE.findall(normalized) if len(token) > 1 or token.isdigit()]


def expand_query(query: str) -> tuple[str, list[str]]:
    normalized = normalize_legal_text(query).casefold()
    terms: list[str] = []
    seen: set[str] = set()

    for token in tokenize(normalized):
        candidates = QUERY_EXPANSIONS.get(token, {token})
        for candidate in candidates:
            # BM25 operates on tokens, so phrase expansions are broken into their
            # deterministic component tokens rather than treated as opaque phrases.
            for expanded_token in tokenize(candidate):
                expanded_token = expanded_token.casefold()
                if expanded_token not in seen:
                    seen.add(expanded_token)
                    terms.append(expanded_token)

    return normalized, terms


def bm25_scores(query_terms: list[str], documents: list[str], *, k1: float = 1.4, b: float = 0.72) -> list[float]:
    if not documents:
        return []
    tokenized = [tokenize(text) for text in documents]
    avgdl = max(sum(len(tokens) for tokens in tokenized) / len(tokenized), 1.0)
    doc_freq: Counter[str] = Counter()
    for tokens in tokenized:
        for term in set(tokens):
            doc_freq[term] += 1

    scores: list[float] = []
    total_docs = len(tokenized)
    for tokens in tokenized:
        freq = Counter(tokens)
        dl = max(len(tokens), 1)
        score = 0.0
        for term in query_terms:
            df = doc_freq.get(term, 0)
            if not df:
                continue
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            tf = freq.get(term, 0)
            if not tf:
                continue
            denom = tf + k1 * (1 - b + b * dl / avgdl)
            score += idf * ((tf * (k1 + 1)) / denom)
        scores.append(score)

    peak = max(scores, default=0.0)
    return [score / peak if peak > 0 else 0.0 for score in scores]


def language_match_score(query: str, text: str) -> float:
    q_deva = bool(re.search(r"[\u0900-\u097F]", query))
    t_deva = bool(re.search(r"[\u0900-\u097F]", text))
    if q_deva == t_deva:
        return 1.0
    # Cross-language retrieval should still rank because expansion maps concepts.
    return 0.72


def authority_score(level: CourtLevel | None, *, bench_strength: int | None = None) -> float:
    if level is None:
        return 0.52
    base = COURT_AUTHORITY.get(level, 0.30)
    if bench_strength and level in {CourtLevel.SUPREME_COURT, CourtLevel.HIGH_COURT}:
        base = min(1.0, base + min(bench_strength - 1, 8) * 0.015)
    return base


def combine_scores(*, lexical: float, authority: float, language: float, exact_reference: bool = False) -> float:
    score = lexical * 0.66 + authority * 0.22 + language * 0.12
    if exact_reference:
        score += 0.12
    return min(score, 1.0)


def make_snippet(text: str, query_terms: list[str], *, radius: int = 210) -> str:
    compact = " ".join(text.split())
    if not compact:
        return ""
    lowered = compact.casefold()
    hits = [lowered.find(term.casefold()) for term in query_terms if lowered.find(term.casefold()) >= 0]
    if not hits:
        return compact[: radius * 2] + ("…" if len(compact) > radius * 2 else "")
    pos = min(hits)
    start = max(0, pos - radius)
    end = min(len(compact), pos + radius)
    prefix = "…" if start else ""
    suffix = "…" if end < len(compact) else ""
    return f"{prefix}{compact[start:end].strip()}{suffix}"
