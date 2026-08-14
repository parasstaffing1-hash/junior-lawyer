from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ChequeTimelineRequest(BaseModel):
    """Dates from the return memo and the notice, if it has gone out."""

    cheque_date: date
    return_memo_date: date
    # Optional: before the notice is sent, the tool projects the windows.
    notice_sent_date: date | None = None
    notice_served_date: date | None = None
    cheque_amount: float | None = Field(default=None, ge=0)


class TimelineStep(BaseModel):
    key: str
    label_en: str
    label_hi: str
    due_date: date | None = None
    completed: bool = False
    overdue: bool = False
    authority: str
    note_en: str | None = None


class ChequeTimelineResponse(BaseModel):
    steps: list[TimelineStep]
    # The two questions a lawyer actually asks.
    notice_deadline: date
    complaint_window_opens: date | None = None
    complaint_deadline: date | None = None
    maintainable: bool
    blocking_reason_en: str | None = None
    blocking_reason_hi: str | None = None
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str
