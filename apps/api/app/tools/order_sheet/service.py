"""Read an order sheet for the next date and what was directed.

The lawyer photographs the order sheet on the way out of court. What they need
from it is small and specific: when is the next date, what stage is it for, and
what must be done before then.

This extracts those deterministically — no model call, so it costs nothing and
behaves the same every time. It handles the two ways Indian order sheets state
a next date: explicitly ("list on 12.09.2026") and relatively ("after four
weeks"), the latter resolved against the order's own date.

Everything is returned `requires_review=True`. An order sheet is often
handwritten, OCR is imperfect, and a wrong date written into the diary is the
precise failure this product exists to prevent. The tool proposes; the lawyer
confirms.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from app.tools.order_sheet.models import (
    ExtractedDate,
    ExtractedDirection,
    OrderSheetRequest,
    OrderSheetResponse,
)

DISCLAIMER = (
    "Deterministic extraction from the text supplied. Order sheets are often "
    "handwritten and OCR is imperfect — confirm every date against the original "
    "before it goes in the diary."
)

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# 12.09.2026 / 12-09-2026 / 12/09/26
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
# 12 September 2026 / 12th Sept, 2026
_TEXT_DATE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b", re.I
)
# "after four weeks", "list after 2 months"
_RELATIVE = re.compile(
    r"\bafter\s+(\d{1,2}|one|two|three|four|five|six|eight|ten|twelve)\s+"
    r"(day|days|week|weeks|month|months)\b",
    re.I,
)
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "eight": 8, "ten": 10, "twelve": 12,
}
_LISTING_CUE = re.compile(
    r"\b(list(?:ed)?|put\s+up|re-?notify|next\s+date|adjourned\s+to|fixed\s+for|"
    r"call\s+on|renotify)\b",
    re.I,
)
_PURPOSE = re.compile(
    r"\bfor\s+((?:final\s+)?arguments|evidence|cross[- ]examination|framing\s+of\s+issues|"
    r"written\s+statement|reply|hearing|orders?|judgment|appearance|steps|"
    r"admission|disposal)\b",
    re.I,
)
_DIRECTION = re.compile(
    r"\b(shall|must|is\s+directed\s+to|are\s+directed\s+to|to\s+file|to\s+produce|"
    r"to\s+furnish|is\s+granted|last\s+opportunity)\b",
    re.I,
)
_PARTY = re.compile(
    r"\b(plaintiff|defendant|petitioner|respondent|applicant|complainant|accused|"
    r"appellant|counsel\s+for\s+\w+)\b",
    re.I,
)
_ADJOURNED = re.compile(r"\badjourn", re.I)
_DISPOSED = re.compile(r"\b(disposed\s+of|dismissed|decreed|allowed|withdrawn)\b", re.I)


def _numeric(match: re.Match) -> date | None:
    day, month, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    try:
        # Indian order sheets are day-first throughout.
        return date(year, month, day)
    except ValueError:
        return None


def _textual(match: re.Match) -> date | None:
    day, month_name, year = match.groups()
    month = _MONTHS.get(month_name.lower().rstrip("."))
    if not month:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _relative(match: re.Match, anchor: date | None) -> date | None:
    if not anchor:
        return None
    raw, unit = match.groups()
    count = _WORD_NUMBERS.get(raw.lower(), None)
    if count is None:
        count = int(raw) if raw.isdigit() else None
    if count is None:
        return None
    unit = unit.lower()
    if unit.startswith("day"):
        return anchor + timedelta(days=count)
    if unit.startswith("week"):
        return anchor + timedelta(weeks=count)
    return anchor + relativedelta(months=count)


def parse_order_sheet(request: OrderSheetRequest) -> OrderSheetResponse:
    text = request.text
    dates: list[ExtractedDate] = []
    listing_candidates: list[tuple[date, bool]] = []

    for line in text.splitlines():
        listing = bool(_LISTING_CUE.search(line))
        for match in _NUMERIC_DATE.finditer(line):
            parsed = _numeric(match)
            dates.append(
                ExtractedDate(
                    raw_text=match.group(0),
                    parsed_date=parsed,
                    kind="listing" if listing else "mentioned",
                    confident=parsed is not None,
                )
            )
            if listing and parsed:
                listing_candidates.append((parsed, True))
        for match in _TEXT_DATE.finditer(line):
            parsed = _textual(match)
            dates.append(
                ExtractedDate(
                    raw_text=match.group(0),
                    parsed_date=parsed,
                    kind="listing" if listing else "mentioned",
                    confident=parsed is not None,
                )
            )
            if listing and parsed:
                listing_candidates.append((parsed, True))
        for match in _RELATIVE.finditer(line):
            parsed = _relative(match, request.order_date)
            dates.append(
                ExtractedDate(
                    raw_text=match.group(0),
                    parsed_date=parsed,
                    kind="relative",
                    # Relative wording is an estimate; the court fixes the day.
                    confident=False,
                )
            )
            if parsed:
                listing_candidates.append((parsed, False))

    next_date: date | None = None
    confident = False
    explicit = [item for item in listing_candidates if item[1]]
    if explicit:
        # The latest explicitly listed date is the next hearing; earlier ones on
        # the sheet are usually references to past listings.
        next_date = max(item[0] for item in explicit)
        confident = True
    elif listing_candidates:
        next_date = max(item[0] for item in listing_candidates)

    purpose_match = _PURPOSE.search(text)
    purpose = purpose_match.group(1).strip() if purpose_match else None

    directions: list[ExtractedDirection] = []
    for sentence in re.split(r"(?<=[.;])\s+|\n", text):
        cleaned = sentence.strip()
        if len(cleaned) < 12 or not _DIRECTION.search(cleaned):
            continue
        party = _PARTY.search(cleaned)
        due = None
        for match in _NUMERIC_DATE.finditer(cleaned):
            due = _numeric(match)
        directions.append(
            ExtractedDirection(
                text=cleaned[:400],
                party_hint=party.group(1).lower() if party else None,
                due_date=due,
            )
        )

    return OrderSheetResponse(
        next_hearing_date=next_date,
        next_hearing_confident=confident,
        purpose=purpose,
        dates=dates,
        directions=directions[:20],
        adjourned=bool(_ADJOURNED.search(text)),
        disposed=bool(_DISPOSED.search(text)),
        requires_review=True,
        disclaimer=DISCLAIMER,
    )
