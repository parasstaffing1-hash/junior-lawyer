import calendar
from datetime import date, timedelta

from app.tools.limitation_period.models import (
    ExpiryAdjustment,
    ExpiryAdjustmentResult,
    LimitationPeriodRequest,
    LimitationPeriodResponse,
    PeriodUnit,
)


DISCLAIMER = (
    "This calculator performs arithmetic using only the period and adjustment rules supplied by the user. "
    "It does not determine which limitation statute applies, when a cause of action accrued, whether time is "
    "suspended or excluded by law, or whether a court holiday rule applies. Verify the result against the "
    "applicable statute, procedural rules, orders, and current case law before relying on it."
)


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _add_months(value: date, months: int) -> date:
    month_index = (value.year * 12 + (value.month - 1)) + months
    target_year, zero_based_month = divmod(month_index, 12)
    target_month = zero_based_month + 1
    target_day = min(value.day, _last_day_of_month(target_year, target_month))
    return date(target_year, target_month, target_day)


def _add_years(value: date, years: int) -> date:
    target_year = value.year + years
    target_day = min(value.day, _last_day_of_month(target_year, value.month))
    return date(target_year, value.month, target_day)


def _add_period(value: date, amount: int, unit: PeriodUnit) -> date:
    if unit == PeriodUnit.DAYS:
        return value + timedelta(days=amount)
    if unit == PeriodUnit.WEEKS:
        return value + timedelta(weeks=amount)
    if unit == PeriodUnit.MONTHS:
        return _add_months(value, amount)
    if unit == PeriodUnit.YEARS:
        return _add_years(value, amount)
    raise ValueError(f"Unsupported period unit: {unit}")


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


def calculate_limitation_period(
    request: LimitationPeriodRequest,
) -> LimitationPeriodResponse:
    excluded_dates = set(request.excluded_dates)
    base_expiry = _add_period(
        request.trigger_date,
        request.period_value,
        request.period_unit,
    )

    total_extension_days = sum(item.days for item in request.extension_periods)
    expiry_before_adjustment = base_expiry + timedelta(days=total_extension_days)
    final_expiry = expiry_before_adjustment
    adjustment_result: ExpiryAdjustmentResult | None = None

    if (
        request.expiry_adjustment == ExpiryAdjustment.NEXT_BUSINESS_DAY
        and _is_non_business_day(
            expiry_before_adjustment,
            excluded_dates,
            request.weekend_weekdays,
        )
    ):
        final_expiry = _roll_forward(
            expiry_before_adjustment,
            excluded_dates,
            request.weekend_weekdays,
        )
        adjustment_result = ExpiryAdjustmentResult(
            original_date=expiry_before_adjustment,
            adjusted_date=final_expiry,
            reason="Expiry fell on a configured weekend or excluded date.",
        )

    notes = [
        f"Base expiry calculated by adding {request.period_value} {request.period_unit.value} to the trigger date.",
        "Month/year arithmetic preserves the day-of-month when possible and clamps to month-end when necessary.",
    ]
    if total_extension_days:
        notes.append(f"Added {total_extension_days} extension day(s) supplied by the user.")
    if adjustment_result:
        notes.append("Rolled the expiry forward to the next configured business day.")

    return LimitationPeriodResponse(
        trigger_date=request.trigger_date,
        period_value=request.period_value,
        period_unit=request.period_unit,
        base_expiry_date=base_expiry,
        total_extension_days=total_extension_days,
        expiry_before_business_day_adjustment=expiry_before_adjustment,
        final_expiry_date=final_expiry,
        expiry_adjustment=adjustment_result,
        excluded_dates_used=sorted(excluded_dates),
        calculation_notes=notes,
        disclaimer=DISCLAIMER,
    )
