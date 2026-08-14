from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class CauseListCase(BaseModel):
    """One of the lawyer's own cases, to be looked for in the list."""

    reference: str = Field(min_length=1, max_length=200)
    matter_id: str | None = None
    title: str | None = Field(default=None, max_length=300)
    party_names: list[str] = Field(default_factory=list, max_length=20)


class CauseListMatchRequest(BaseModel):
    # The pasted or transcribed cause list, one entry per line.
    cause_list_text: str = Field(min_length=1, max_length=200_000)
    cases: list[CauseListCase] = Field(min_length=1, max_length=500)
    list_date: date | None = None
    court_name: str | None = Field(default=None, max_length=250)


class CauseListMatch(BaseModel):
    reference: str
    matter_id: str | None = None
    title: str | None = None
    line_number: int
    line_text: str
    item_number: str | None = None
    matched_on: str
    confident: bool


class CauseListMatchResponse(BaseModel):
    list_date: date | None = None
    court_name: str | None = None
    total_lines: int
    matches: list[CauseListMatch]
    unmatched_references: list[str]
    # Lines that look like a listing but matched nothing — worth an eye, because
    # a case can appear under a number the lawyer does not have on file.
    review_lines: list[str] = Field(default_factory=list)
    disclaimer: str
