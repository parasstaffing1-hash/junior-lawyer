import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext

from app.tools.claim_interest.models import (
    ClaimInterestCalculationRequest,
    ClaimInterestCalculationResponse,
    CompoundingFrequency,
    DayCountConvention,
    InterestBreakdownLine,
    InterestMethod,
)

DISCLAIMER = (
    "This calculator performs deterministic interest arithmetic from the inputs provided. "
    "It does not determine the legally applicable rate, start date, end date, compounding "
    "entitlement, payment-allocation rule, or statutory/court discretion. Verify those inputs "
    "against the governing law, contract, order, and current court practice."
)


class ClaimInterestInputError(ValueError):
    pass


FREQUENCIES = {
    CompoundingFrequency.ANNUAL: Decimal("1"),
    CompoundingFrequency.SEMIANNUAL: Decimal("2"),
    CompoundingFrequency.QUARTERLY: Decimal("4"),
    CompoundingFrequency.MONTHLY: Decimal("12"),
    CompoundingFrequency.DAILY: Decimal("365"),
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _is_leap(year: int) -> bool:
    return calendar.isleap(year)


def _actual_actual_fraction(start: date, end: date) -> Decimal:
    current = start
    fraction = Decimal("0")
    while current < end:
        next_year = date(current.year + 1, 1, 1)
        segment_end = min(end, next_year)
        days = Decimal((segment_end - current).days)
        denominator = Decimal("366" if _is_leap(current.year) else "365")
        fraction += days / denominator
        current = segment_end
    return fraction


def _thirty_360_fraction(start: date, end: date) -> Decimal:
    # 30E/360-style deterministic convention: clamp each day to 30.
    d1 = min(start.day, 30)
    d2 = min(end.day, 30)
    days360 = (
        (end.year - start.year) * 360
        + (end.month - start.month) * 30
        + (d2 - d1)
    )
    return Decimal(days360) / Decimal("360")


def year_fraction(
    start: date,
    end: date,
    convention: DayCountConvention,
) -> Decimal:
    if end < start:
        raise ClaimInterestInputError("period end cannot be before period start")

    days = Decimal((end - start).days)
    if convention == DayCountConvention.ACTUAL_365:
        return days / Decimal("365")
    if convention == DayCountConvention.ACTUAL_366:
        return days / Decimal("366")
    if convention == DayCountConvention.ACTUAL_360:
        return days / Decimal("360")
    if convention == DayCountConvention.ACTUAL_ACTUAL:
        return _actual_actual_fraction(start, end)
    if convention == DayCountConvention.THIRTY_360:
        return _thirty_360_fraction(start, end)
    raise ClaimInterestInputError(f"unsupported day-count convention: {convention}")


def _simple_interest(
    principal: Decimal,
    annual_rate: Decimal,
    fraction: Decimal,
) -> Decimal:
    return principal * annual_rate * fraction


def _compound_interest(
    principal: Decimal,
    annual_rate: Decimal,
    fraction: Decimal,
    frequency: CompoundingFrequency,
) -> Decimal:
    periods_per_year = FREQUENCIES[frequency]
    if annual_rate == 0 or fraction == 0:
        return Decimal("0")

    # Decimal supports fractional powers through exp/ln in Python 3.11+.
    # Use elevated precision for stable money results before final rounding.
    with localcontext() as ctx:
        ctx.prec = 34
        base = Decimal("1") + (annual_rate / periods_per_year)
        exponent = periods_per_year * fraction
        growth = (exponent * base.ln()).exp()
        return principal * (growth - Decimal("1"))


def calculate_claim_interest(
    request: ClaimInterestCalculationRequest,
) -> ClaimInterestCalculationResponse:
    rate = request.annual_rate_percent / Decimal("100")

    adjustments_by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    notes_by_date: dict[date, list[str]] = defaultdict(list)
    for adjustment in request.principal_adjustments:
        adjustments_by_date[adjustment.date] += adjustment.amount
        if adjustment.note:
            notes_by_date[adjustment.date].append(adjustment.note)

    boundaries = sorted({request.start_date, request.end_date, *adjustments_by_date.keys()})

    outstanding_principal = request.principal
    accrued_simple_interest = Decimal("0")
    total_adjustments = Decimal("0")
    breakdown: list[InterestBreakdownLine] = []

    for index in range(len(boundaries) - 1):
        period_start = boundaries[index]
        period_end = boundaries[index + 1]
        opening = outstanding_principal
        fraction = year_fraction(
            period_start,
            period_end,
            request.day_count_convention,
        )

        if request.method == InterestMethod.SIMPLE:
            interest = _simple_interest(opening, rate, fraction)
            accrued_simple_interest += interest
            pre_adjustment_principal = opening
        else:
            interest = _compound_interest(
                opening,
                rate,
                fraction,
                request.compounding_frequency,
            )
            pre_adjustment_principal = opening + interest

        adjustment = adjustments_by_date.get(period_end, Decimal("0"))
        closing = pre_adjustment_principal + adjustment
        if closing < 0:
            raise ClaimInterestInputError(
                f"principal adjustment on {period_end.isoformat()} reduces outstanding "
                "principal below zero"
            )

        total_adjustments += adjustment
        outstanding_principal = closing

        note_parts = notes_by_date.get(period_end, [])
        breakdown.append(
            InterestBreakdownLine(
                period_start=period_start,
                period_end=period_end,
                days=(period_end - period_start).days,
                year_fraction=fraction.quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP),
                opening_principal=_money(opening),
                annual_rate_percent=request.annual_rate_percent,
                method=request.method,
                interest=_money(interest),
                adjustment_at_period_end=_money(adjustment),
                closing_principal=_money(closing),
                note="; ".join(note_parts) if note_parts else None,
            )
        )

    if request.method == InterestMethod.SIMPLE:
        final_principal = outstanding_principal
        total_interest = accrued_simple_interest
        total_amount = final_principal + total_interest
        compounding_frequency = None
    else:
        final_principal = outstanding_principal
        total_interest = final_principal - request.principal - total_adjustments
        total_amount = final_principal
        compounding_frequency = request.compounding_frequency

    return ClaimInterestCalculationResponse(
        currency=request.currency.upper(),
        principal=_money(request.principal),
        annual_rate_percent=request.annual_rate_percent,
        start_date=request.start_date,
        end_date=request.end_date,
        method=request.method,
        day_count_convention=request.day_count_convention,
        compounding_frequency=compounding_frequency,
        total_days=(request.end_date - request.start_date).days,
        total_adjustments=_money(total_adjustments),
        total_interest=_money(total_interest),
        final_principal=_money(final_principal),
        total_amount=_money(total_amount),
        breakdown=breakdown,
        disclaimer=DISCLAIMER,
    )
