from datetime import date, timedelta

from app.tools.legal_deadline.models import (
    CountMode,
    DeadlineAdjustment,
    LegalDeadlineRequest,
    LegalDeadlineResponse,
)


DISCLAIMER = (
    "This calculator applies the supplied counting rules only. "
    "Court, statute, service-method, emergency, and jurisdiction-specific rules "
    "may change a legal deadline. Verify the result against the applicable law and court rules."
)


def _is_non_business_day(
    value: date,
    excluded_dates: set[date],
    weekend_weekdays: set[int],
) -> bool:
    return value.weekday() in weekend_weekdays or value in excluded_dates


def _roll_forward(
    value: date,
    excluded_dates: set[date],
    weekend_weekdays: set[int],
) -> date:
    current = value
    while _is_non_business_day(current, excluded_dates, weekend_weekdays):
        current += timedelta(days=1)
    return current


def _count_calendar_days(request: LegalDeadlineRequest) -> date:
    if request.days == 0:
        return request.start_date

    offset = request.days - 1 if request.include_start_date else request.days
    return request.start_date + timedelta(days=offset)


def _count_business_days(
    request: LegalDeadlineRequest,
    excluded_dates: set[date],
) -> date:
    if request.days == 0:
        return request.start_date

    current = request.start_date
    counted = 0

    if request.include_start_date and not _is_non_business_day(
        current,
        excluded_dates,
        request.weekend_weekdays,
    ):
        counted = 1

    while counted < request.days:
        current += timedelta(days=1)
        if not _is_non_business_day(
            current,
            excluded_dates,
            request.weekend_weekdays,
        ):
            counted += 1

    return current


def calculate_deadline(request: LegalDeadlineRequest) -> LegalDeadlineResponse:
    excluded_dates = set(request.excluded_dates)

    if request.count_mode == CountMode.BUSINESS_DAYS:
        due_date = _count_business_days(request, excluded_dates)
    else:
        due_date = _count_calendar_days(request)

    adjustment: DeadlineAdjustment | None = None

    if request.roll_if_non_business and _is_non_business_day(
        due_date,
        excluded_dates,
        request.weekend_weekdays,
    ):
        adjusted = _roll_forward(
            due_date,
            excluded_dates,
            request.weekend_weekdays,
        )
        adjustment = DeadlineAdjustment(
            original_date=due_date,
            adjusted_date=adjusted,
            reason="Due date fell on an excluded date or configured weekend.",
        )
        due_date = adjusted

    return LegalDeadlineResponse(
        start_date=request.start_date,
        due_date=due_date,
        days=request.days,
        count_mode=request.count_mode,
        include_start_date=request.include_start_date,
        excluded_dates_used=sorted(excluded_dates),
        adjustment=adjustment,
        disclaimer=DISCLAIMER,
    )
