from __future__ import annotations

import re
from collections import Counter

from app.tools.legal_citation.models import (
    CitationExtractRequest,
    CitationExtractResponse,
    CitationFormatRequest,
    CitationFormatResponse,
    CitationKind,
    CitationMatch,
)


DISCLAIMER = (
    "This deterministic utility formats and extracts supported citation patterns only. "
    "It does not verify that a cited case exists, that a citation is authoritative, or that "
    "the format complies with a particular court, journal, filing rule, or style guide."
)


class LegalCitationError(ValueError):
    pass


PATTERNS: dict[CitationKind, re.Pattern[str]] = {
    CitationKind.SCC: re.compile(
        r"\((?P<year>(?:18|19|20|21)\d{2})\)\s*(?P<volume>\d{1,3})\s+SCC\s+(?P<number>\d{1,8})\b",
        re.IGNORECASE,
    ),
    CitationKind.AIR: re.compile(
        r"\bAIR\s+(?P<year>(?:18|19|20|21)\d{2})\s+(?P<court>[A-Z][A-Z.]{1,15})\s+(?P<number>\d{1,8})\b",
        re.IGNORECASE,
    ),
    CitationKind.SCC_ONLINE: re.compile(
        r"\b(?P<year>(?:19|20|21)\d{2})\s+SCC\s+OnLine\s+(?P<court>[A-Za-z][A-Za-z.]{1,15})\s+(?P<number>\d{1,8})\b",
        re.IGNORECASE,
    ),
    CitationKind.INDIA_NEUTRAL: re.compile(
        r"\b(?P<year>(?:20|21)\d{2})\s*[: ]\s*(?P<court>INSC|INHC|DHC|BHC|KARHC|MHC|KERHC|CALHC)\s*[: ]\s*(?P<number>\d{1,8})\b",
        re.IGNORECASE,
    ),
    CitationKind.UK_NEUTRAL: re.compile(
        r"\[(?P<year>(?:19|20|21)\d{2})\]\s+(?P<court>UKSC|UKPC|EWHC|EWCA)(?:\s+(?P<division>Civ|Crim|Admin|Ch|Fam|Comm))?\s+(?P<number>\d{1,8})\b",
        re.IGNORECASE,
    ),
}


def _clean_code(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    if not re.fullmatch(r"[A-Za-z.]+", cleaned):
        raise LegalCitationError("court_code and division may contain letters and periods only")
    return cleaned.upper()


def _format(kind: CitationKind, *, year: int, volume: int | None, number: int, court: str | None, division: str | None) -> str:
    if kind == CitationKind.SCC:
        if volume is None:
            raise LegalCitationError("volume is required for SCC citations")
        return f"({year}) {volume} SCC {number}"
    if kind == CitationKind.AIR:
        if not court:
            raise LegalCitationError("court_code is required for AIR citations")
        return f"AIR {year} {court} {number}"
    if kind == CitationKind.SCC_ONLINE:
        if not court:
            raise LegalCitationError("court_code is required for SCC OnLine citations")
        return f"{year} SCC OnLine {court} {number}"
    if kind == CitationKind.INDIA_NEUTRAL:
        if not court:
            raise LegalCitationError("court_code is required for India neutral citations")
        return f"{year} {court} {number}"
    if kind == CitationKind.UK_NEUTRAL:
        if not court:
            raise LegalCitationError("court_code is required for UK neutral citations")
        suffix = f" {division}" if division else ""
        return f"[{year}] {court}{suffix} {number}"
    raise LegalCitationError(f"unsupported citation kind: {kind}")


def format_citation(payload: CitationFormatRequest) -> CitationFormatResponse:
    court = _clean_code(payload.court_code)
    division = _clean_code(payload.division)
    warnings: list[str] = []

    if payload.kind == CitationKind.UK_NEUTRAL and court == "EWCA" and division not in {"CIV", "CRIM"}:
        warnings.append("EWCA division is usually Civ or Crim; verify the required court style.")

    citation = _format(
        payload.kind,
        year=payload.year,
        volume=payload.volume,
        number=payload.page_or_number,
        court=court,
        division=division.title() if division else None,
    )
    case_name = " ".join(payload.case_name.split()) if payload.case_name else None
    with_name = f"{case_name}, {citation}" if case_name else citation
    return CitationFormatResponse(
        kind=payload.kind,
        citation=citation,
        citation_with_case_name=with_name,
        normalized_fields={
            "year": payload.year,
            "volume": payload.volume,
            "page_or_number": payload.page_or_number,
            "court_code": court,
            "division": division.title() if division else None,
            "case_name": case_name,
        },
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )


def _line_column(text: str, start: int) -> tuple[int, int]:
    line = text.count("\n", 0, start) + 1
    last_newline = text.rfind("\n", 0, start)
    column = start + 1 if last_newline == -1 else start - last_newline
    return line, column


def _match_to_citation(kind: CitationKind, match: re.Match[str], text: str) -> CitationMatch:
    groups = match.groupdict()
    year = int(groups["year"])
    volume = int(groups["volume"]) if groups.get("volume") else None
    number = int(groups["number"])
    court = groups.get("court")
    division = groups.get("division")
    court_norm = court.upper() if court else None
    division_norm = division.title() if division else None

    normalized = _format(
        kind,
        year=year,
        volume=volume,
        number=number,
        court=court_norm,
        division=division_norm,
    )
    line, column = _line_column(text, match.start())
    return CitationMatch(
        kind=kind,
        raw=match.group(0),
        normalized=normalized,
        start=match.start(),
        end=match.end(),
        line=line,
        column=column,
        fields={
            "year": year,
            "volume": volume,
            "page_or_number": number,
            "court_code": court_norm,
            "division": division_norm,
        },
    )


def extract_citations(payload: CitationExtractRequest) -> CitationExtractResponse:
    kinds = payload.kinds or list(CitationKind)
    kinds = list(dict.fromkeys(kinds))
    raw_matches: list[CitationMatch] = []

    for kind in kinds:
        pattern = PATTERNS[kind]
        for match in pattern.finditer(payload.text):
            raw_matches.append(_match_to_citation(kind, match, payload.text))

    raw_matches.sort(key=lambda item: (item.start, item.end, item.kind.value))
    total_detected = len(raw_matches)

    if payload.deduplicate:
        seen: set[tuple[CitationKind, str]] = set()
        matches: list[CitationMatch] = []
        for item in raw_matches:
            key = (item.kind, item.normalized.casefold())
            if key in seen:
                continue
            seen.add(key)
            matches.append(item)
    else:
        matches = raw_matches

    counts = Counter(item.kind.value for item in matches)
    unique_normalized = {(item.kind.value, item.normalized.casefold()) for item in raw_matches}
    warnings: list[str] = []
    if not raw_matches:
        warnings.append("No supported citation pattern was detected in the supplied text.")
    elif payload.deduplicate and len(matches) < total_detected:
        warnings.append(f"Removed {total_detected - len(matches)} repeated citation occurrence(s).")

    return CitationExtractResponse(
        matches=matches,
        match_count=len(matches),
        unique_count=len(unique_normalized),
        kinds_found=dict(sorted(counts.items())),
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
