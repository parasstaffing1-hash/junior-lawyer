from __future__ import annotations

import re
from dataclasses import dataclass

CNR_RE = re.compile(r"^[A-Z]{4}[0-9A-Z]{12}$", re.IGNORECASE)
CASE_RE = re.compile(
    # Unicode-friendly case-type prefix. We preserve the court's own label rather than guessing
    # that a Hindi/English/Hinglish phrase maps to a particular court abbreviation.
    r"^(?:(?P<case_type>[^\d/]{1,50}?)\s+)?(?P<number>\d{1,10})\s*(?:/|OF|of|में)?\s*(?P<year>19\d{2}|20\d{2}|21\d{2})$"
)


@dataclass(frozen=True, slots=True)
class ParsedCaseQuery:
    kind: str
    raw: str
    cnr: str | None = None
    case_type: str | None = None
    case_number: str | None = None
    year: int | None = None

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "raw": self.raw,
            "cnr": self.cnr,
            "case_type": self.case_type,
            "case_number": self.case_number,
            "year": self.year,
        }


def normalize_cnr(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def normalize_case_type(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip()).upper()
    return cleaned or None


def parse_case_query(value: str) -> ParsedCaseQuery:
    raw = re.sub(r"\s+", " ", value.strip())
    normalized = normalize_cnr(raw)
    if CNR_RE.fullmatch(normalized):
        return ParsedCaseQuery(kind="cnr", raw=raw, cnr=normalized)

    match = CASE_RE.fullmatch(raw)
    if match:
        case_type = normalize_case_type(match.group("case_type"))
        return ParsedCaseQuery(
            kind="case_number",
            raw=raw,
            case_type=case_type,
            case_number=match.group("number"),
            year=int(match.group("year")),
        )

    # A bare case number is still useful if court/location preferences narrow it later.
    if raw.isdigit():
        return ParsedCaseQuery(kind="bare_number", raw=raw, case_number=raw)
    return ParsedCaseQuery(kind="free_text", raw=raw)


def rank_case_record(record: dict, parsed: ParsedCaseQuery, *, state: str | None = None, district: str | None = None, court: str | None = None) -> int:
    score = 0
    if parsed.cnr and normalize_cnr(str(record.get("cnr") or "")) == parsed.cnr:
        return 100
    if parsed.case_number and str(record.get("case_number") or "").casefold() == parsed.case_number.casefold():
        score += 35
    if parsed.year and record.get("year") == parsed.year:
        score += 20
    if parsed.case_type and normalize_case_type(str(record.get("case_type") or "")) == parsed.case_type:
        score += 20
    if state and state.casefold() in str(record.get("state") or "").casefold():
        score += 10
    if district and district.casefold() in str(record.get("district") or "").casefold():
        score += 10
    if court and court.casefold() in str(record.get("court_name") or "").casefold():
        score += 10
    if parsed.kind == "free_text":
        haystack = " ".join(str(record.get(key) or "") for key in ("case_title", "case_number", "cnr", "court_name", "district", "state"))
        terms = [term.casefold() for term in parsed.raw.split() if len(term) > 1]
        if terms:
            hits = sum(1 for term in terms if term in haystack.casefold())
            score += min(60, hits * 12)
    return min(score, 100)
