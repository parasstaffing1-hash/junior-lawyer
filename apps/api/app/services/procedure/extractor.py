from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ExtractedDirection:
    text: str
    due_date: date | None
    confidence: int
    metadata: dict


DIRECTION_PATTERNS = [
    re.compile(r"(?i)\b(?:is|are)\s+directed\s+to\b"),
    re.compile(r"(?i)\bshall\s+(?:file|furnish|serve|submit|produce|deposit|comply)\b"),
    re.compile(r"(?i)\b(?:file|furnish|serve|submit|produce|deposit)\b.{0,80}\bwithin\b"),
    re.compile(r"(?:निर्देश\s+दिया\s+जाता\s+है|निर्देशित\s+किया\s+जाता\s+है|दाखिल\s+करें|प्रस्तुत\s+करें|जमा\s+करें)"),
]
WITHIN_DAYS = re.compile(r"(?i)\bwithin\s+(\d{1,3})\s+days?\b")
HINDI_DAYS = re.compile(r"(\d{1,3})\s*(?:दिन|दिनों)\s*(?:के\s*)?(?:भीतर|अंदर)")


def extract_directions(text: str, *, order_date: date | None = None) -> list[ExtractedDirection]:
    if not text.strip():
        return []
    pieces = [piece.strip() for piece in re.split(r"(?<=[.;।])\s+|\n+", text) if piece.strip()]
    results: list[ExtractedDirection] = []
    seen: set[str] = set()
    for piece in pieces:
        if len(piece) < 12 or not any(pattern.search(piece) for pattern in DIRECTION_PATTERNS):
            continue
        key = re.sub(r"\s+", " ", piece).casefold()
        if key in seen:
            continue
        seen.add(key)
        days: int | None = None
        match = WITHIN_DAYS.search(piece) or HINDI_DAYS.search(piece)
        if match:
            days = int(match.group(1))
        due = order_date + timedelta(days=days) if order_date and days is not None else None
        confidence = 92 if days is not None else 82
        results.append(ExtractedDirection(
            text=piece,
            due_date=due,
            confidence=confidence,
            metadata={
                "relative_days_detected": days,
                "calculation_is_provisional": days is not None,
                "note": "Extracted directions and relative dates require lawyer review.",
            },
        ))
    return results
