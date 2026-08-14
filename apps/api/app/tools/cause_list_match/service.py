"""Find the lawyer's own cases in a pasted cause list.

Every morning a district lawyer reads a board or a PDF looking for their own
matters among a few hundred entries. This does that mechanically.

Matching is deterministic and deliberately conservative:

  * case numbers are normalised before comparison, because the same case is
    written "CS 234/2026", "C.S. No. 234 of 2026" and "CS/234/2026" on three
    different lists;
  * a number match is reported as confident; a party-name match is not, because
    "Ram Singh" appears on many lists and the lawyer must look;
  * lines that look like listings but match nothing are returned for review
    rather than dropped — a case can be listed under a number the lawyer does
    not have on file, and silently omitting it is the one failure that costs a
    date.

No fuzzy scoring. A near-miss presented as a match is worse than an honest
"not found", because the lawyer stops looking.
"""

from __future__ import annotations

import re

from app.tools.cause_list_match.models import (
    CauseListMatch,
    CauseListMatchRequest,
    CauseListMatchResponse,
)

DISCLAIMER = (
    "Mechanical text matching against the list supplied. Always confirm against "
    "the court's own board — a case can be listed under a number or spelling "
    "this tool has not been given."
)

# "12." or "12)" at the start of a line, the item's serial on the board.
_ITEM_NUMBER = re.compile(r"^\s*(\d{1,4})\s*[.)\]]\s+")
# Anything shaped like a case number: letters, then digits/digits.
_CASE_SHAPE = re.compile(r"[A-Za-z][A-Za-z.\s]{0,14}?\d{1,6}\s*(?:/|\s+of\s+|\s+)\s*\d{2,4}")


def normalise_case_number(value: str) -> str:
    """Reduce a case number to comparable form.

    "C.S. No. 234 of 2026", "CS 234/2026" and "cs/234/2026" all become
    "cs2342026", so the same case matches however the list writes it.
    """
    lowered = (value or "").lower()
    lowered = re.sub(r"\b(no|nos|case|of)\b", " ", lowered)
    return re.sub(r"[^a-z0-9]", "", lowered)


def _normalise_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def match_cause_list(request: CauseListMatchRequest) -> CauseListMatchResponse:
    lines = [line.rstrip() for line in request.cause_list_text.splitlines()]
    matches: list[CauseListMatch] = []
    matched_references: set[str] = set()
    matched_line_numbers: set[int] = set()

    prepared = [
        (
            case,
            normalise_case_number(case.reference),
            [_normalise_name(name) for name in case.party_names if len(name.strip()) >= 4],
        )
        for case in request.cases
    ]

    for index, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        normalised_line = normalise_case_number(raw)
        lowered_line = _normalise_name(raw)
        item = _ITEM_NUMBER.match(raw)
        item_number = item.group(1) if item else None

        for case, reference_key, names in prepared:
            if reference_key and reference_key in normalised_line:
                matches.append(
                    CauseListMatch(
                        reference=case.reference,
                        matter_id=case.matter_id,
                        title=case.title,
                        line_number=index,
                        line_text=raw.strip(),
                        item_number=item_number,
                        matched_on="case_number",
                        confident=True,
                    )
                )
                matched_references.add(case.reference)
                matched_line_numbers.add(index)
                break

            hit = next((name for name in names if name and name in lowered_line), None)
            if hit:
                matches.append(
                    CauseListMatch(
                        reference=case.reference,
                        matter_id=case.matter_id,
                        title=case.title,
                        line_number=index,
                        line_text=raw.strip(),
                        item_number=item_number,
                        matched_on=f"party_name:{hit}",
                        # A shared name is not proof; the lawyer must look.
                        confident=False,
                    )
                )
                matched_references.add(case.reference)
                matched_line_numbers.add(index)
                break

    review = [
        line.strip()
        for index, line in enumerate(lines, start=1)
        if index not in matched_line_numbers
        and line.strip()
        and _CASE_SHAPE.search(line)
    ]

    return CauseListMatchResponse(
        list_date=request.list_date,
        court_name=request.court_name,
        total_lines=sum(1 for line in lines if line.strip()),
        matches=sorted(matches, key=lambda item: item.line_number),
        unmatched_references=[
            case.reference for case in request.cases if case.reference not in matched_references
        ],
        review_lines=review[:50],
        disclaimer=DISCLAIMER,
    )
