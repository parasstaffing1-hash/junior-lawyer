from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class OrderSheetRequest(BaseModel):
    """Text of an order sheet, typed or produced by OCR."""

    text: str = Field(min_length=1, max_length=100_000)
    # Anchors relative dates such as "after four weeks".
    order_date: date | None = None


class ExtractedDate(BaseModel):
    raw_text: str
    parsed_date: date | None = None
    kind: str
    confident: bool


class ExtractedDirection(BaseModel):
    text: str
    party_hint: str | None = None
    due_date: date | None = None


class OrderSheetResponse(BaseModel):
    next_hearing_date: date | None = None
    next_hearing_confident: bool = False
    purpose: str | None = None
    dates: list[ExtractedDate] = Field(default_factory=list)
    directions: list[ExtractedDirection] = Field(default_factory=list)
    adjourned: bool = False
    disposed: bool = False
    # Everything here needs a human eye before it reaches the diary.
    requires_review: bool = True
    disclaimer: str
