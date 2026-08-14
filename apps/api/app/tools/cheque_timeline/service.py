"""The section 138 clock.

A cheque-bounce complaint fails on dates far more often than on merits, and the
dates are unforgiving:

  * the cheque must be presented within its validity — three months — or the
    dishonour does not attract section 138 at all;
  * the demand notice must go out within 30 days of the return memo;
  * the drawer then has 15 days to pay, and a complaint filed before that
    period expires is premature;
  * the complaint must be filed within the month after those 15 days end.

This computes each of those and says plainly whether the complaint is
maintainable today. Every step names the provision it comes from so a lawyer
can check it rather than trust it.

The arithmetic is deterministic and needs no rule pack. Court holidays are not
applied: the outer limit under section 142(1)(b) is a limitation period, and
whether a local holiday extends it is a question for the lawyer, not a default
this tool should quietly assume.
"""

from __future__ import annotations

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from app.tools.cheque_timeline.models import (
    ChequeTimelineRequest,
    ChequeTimelineResponse,
    TimelineStep,
)

CHEQUE_VALIDITY_MONTHS = 3
NOTICE_WINDOW_DAYS = 30
PAYMENT_WINDOW_DAYS = 15

DISCLAIMER = (
    "Deterministic date arithmetic under the Negotiable Instruments Act, 1881. "
    "Court holidays and any local practice on computing the limitation period "
    "are not applied. Verify against the Act and the court's own reckoning "
    "before filing."
)


class ChequeTimelineInputError(ValueError):
    """The dates given cannot describe a real dishonour."""


def calculate_cheque_timeline(request: ChequeTimelineRequest) -> ChequeTimelineResponse:
    if request.return_memo_date < request.cheque_date:
        raise ChequeTimelineInputError(
            "The return memo cannot pre-date the cheque."
        )
    if request.notice_sent_date and request.notice_sent_date < request.return_memo_date:
        raise ChequeTimelineInputError(
            "The notice cannot be sent before the cheque was returned."
        )
    if (
        request.notice_served_date
        and request.notice_sent_date
        and request.notice_served_date < request.notice_sent_date
    ):
        raise ChequeTimelineInputError("Service cannot pre-date despatch.")

    today = date.today()
    warnings: list[str] = []
    steps: list[TimelineStep] = []

    # 1. Presentation within validity.
    validity_end = request.cheque_date + relativedelta(months=CHEQUE_VALIDITY_MONTHS)
    presented_in_time = request.return_memo_date <= validity_end
    steps.append(
        TimelineStep(
            key="presentation",
            label_en="Cheque presented within validity",
            label_hi="वैधता अवधि में चेक प्रस्तुत",
            due_date=validity_end,
            completed=presented_in_time,
            overdue=not presented_in_time,
            authority="Section 138 proviso (a), Negotiable Instruments Act, 1881",
            note_en=f"Cheque valid for {CHEQUE_VALIDITY_MONTHS} months from its date.",
        )
    )
    if not presented_in_time:
        warnings.append(
            "The cheque was returned after its validity expired, so the dishonour "
            "may not attract section 138 at all."
        )

    # 2. Demand notice within 30 days of the return memo.
    notice_deadline = request.return_memo_date + timedelta(days=NOTICE_WINDOW_DAYS)
    notice_sent = request.notice_sent_date is not None
    notice_late = notice_sent and request.notice_sent_date > notice_deadline
    steps.append(
        TimelineStep(
            key="notice",
            label_en="Demand notice despatched",
            label_hi="मांग नोटिस भेजा गया",
            due_date=notice_deadline,
            completed=notice_sent and not notice_late,
            overdue=notice_late or (not notice_sent and today > notice_deadline),
            authority="Section 138 proviso (b), Negotiable Instruments Act, 1881",
            note_en=f"Within {NOTICE_WINDOW_DAYS} days of the return memo.",
        )
    )
    if notice_late:
        warnings.append(
            "The demand notice went out after the 30-day window; the cause of "
            "action under section 138 does not arise on this dishonour."
        )
    elif not notice_sent and today > notice_deadline:
        warnings.append(
            "The 30-day notice window has passed with no notice recorded. A fresh "
            "presentation of the cheque may be the only route left."
        )

    # 3. Fifteen days for the drawer to pay, running from service.
    reference = request.notice_served_date or request.notice_sent_date
    payment_deadline = reference + timedelta(days=PAYMENT_WINDOW_DAYS) if reference else None
    if request.notice_sent_date and not request.notice_served_date:
        warnings.append(
            "Service date not recorded — the 15-day period runs from service, not "
            "despatch, so these dates are provisional."
        )
    steps.append(
        TimelineStep(
            key="payment_window",
            label_en="15 days for the drawer to pay",
            label_hi="भुगतान हेतु 15 दिन",
            due_date=payment_deadline,
            completed=bool(payment_deadline and today > payment_deadline),
            overdue=False,
            authority="Section 138 proviso (c), Negotiable Instruments Act, 1881",
            note_en="A complaint filed before this expires is premature.",
        )
    )

    # 4. Complaint within one month of the payment window closing.
    complaint_opens = payment_deadline + timedelta(days=1) if payment_deadline else None
    complaint_deadline = (
        payment_deadline + relativedelta(months=1) if payment_deadline else None
    )
    steps.append(
        TimelineStep(
            key="complaint",
            label_en="Complaint filed",
            label_hi="परिवाद दायर",
            due_date=complaint_deadline,
            completed=False,
            overdue=bool(complaint_deadline and today > complaint_deadline),
            authority="Section 142(1)(b), Negotiable Instruments Act, 1881",
            note_en="One month from the day the 15-day period ends. Delay needs a "
            "condonation application under the proviso to section 142(1)(b).",
        )
    )
    if complaint_deadline and today > complaint_deadline:
        warnings.append(
            "The one-month filing window has closed. A complaint now needs an "
            "application to condone the delay."
        )

    maintainable = True
    blocking_en: str | None = None
    blocking_hi: str | None = None
    if not presented_in_time:
        maintainable = False
        blocking_en = "The cheque was presented after its three-month validity."
        blocking_hi = "चेक तीन माह की वैधता के बाद प्रस्तुत किया गया।"
    elif notice_late:
        maintainable = False
        blocking_en = "The demand notice was issued after the 30-day window."
        blocking_hi = "मांग नोटिस 30 दिन की अवधि के बाद जारी किया गया।"
    elif payment_deadline and today <= payment_deadline:
        maintainable = False
        blocking_en = (
            f"Premature: the drawer has until {payment_deadline.isoformat()} to pay."
        )
        blocking_hi = f"समयपूर्व: भुगतान हेतु {payment_deadline.isoformat()} तक समय है।"

    return ChequeTimelineResponse(
        steps=steps,
        notice_deadline=notice_deadline,
        complaint_window_opens=complaint_opens,
        complaint_deadline=complaint_deadline,
        maintainable=maintainable,
        blocking_reason_en=blocking_en,
        blocking_reason_hi=blocking_hi,
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
