from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedCitation:
    raw: str
    normalized: str
    reporter: str
    year: int | None = None
    volume: int | None = None
    court: str | None = None
    page_or_number: int | None = None


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "SCC",
        re.compile(
            r"\((?P<year>\d{4})\)\s*(?P<volume>\d+)\s*SCC\s*(?P<number>\d+)",
            re.IGNORECASE,
        ),
    ),
    (
        "SCC_ONLINE",
        re.compile(
            r"\b(?P<year>\d{4})\s*SCC\s+OnLine\s+(?P<court>[A-Za-z]{2,20})\s+(?P<number>\d+)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "AIR",
        re.compile(
            r"\bAIR\s+(?P<year>\d{4})\s+(?P<court>[A-Za-z]{2,20})\s+(?P<number>\d+)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "INSC",
        re.compile(r"\b(?P<year>\d{4})\s+INSC\s+(?P<number>\d+)\b", re.IGNORECASE),
    ),
    (
        "NEUTRAL",
        re.compile(r"\b(?P<year>\d{4}):(?P<court>[A-Z]{2,15}):(?P<number>\d+)\b"),
    ),
]


def normalize_citation(raw: str) -> str:
    text = " ".join(raw.replace("\u00a0", " ").split()).strip(" ,.;")
    return text.upper().replace("SCC ONLINE", "SCC ONLINE")


def parse_citations(text: str) -> list[ParsedCitation]:
    parsed: list[ParsedCitation] = []
    seen: set[tuple[int, int, str]] = set()

    for reporter, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            key = (match.start(), match.end(), reporter)
            if key in seen:
                continue
            seen.add(key)
            groups = match.groupdict()
            parsed.append(
                ParsedCitation(
                    raw=match.group(0),
                    normalized=normalize_citation(match.group(0)),
                    reporter=reporter,
                    year=int(groups["year"]) if groups.get("year") else None,
                    volume=int(groups["volume"]) if groups.get("volume") else None,
                    court=groups.get("court").upper() if groups.get("court") else None,
                    page_or_number=int(groups["number"]) if groups.get("number") else None,
                )
            )

    parsed.sort(key=lambda item: text.find(item.raw))
    return parsed
