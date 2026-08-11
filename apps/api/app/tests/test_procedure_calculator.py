from datetime import date

from app.models.procedure import DayBasis, DeadlineAdjustment
from app.services.procedure.calculator import calculate_deadline, is_working_day


def test_calendar_days_count_from_next_day():
    result = calculate_deadline(date(2026, 8, 8), offset_days=3)
    assert result.calculated_date == date(2026, 8, 11)
    assert result.due_date == date(2026, 8, 11)


def test_business_days_skip_weekend():
    result = calculate_deadline(
        date(2026, 8, 7),
        offset_days=3,
        day_basis=DayBasis.BUSINESS,
    )
    assert result.due_date == date(2026, 8, 12)
    assert result.skipped_weekends == 2


def test_business_days_skip_supplied_holiday():
    result = calculate_deadline(
        date(2026, 8, 7),
        offset_days=2,
        day_basis=DayBasis.BUSINESS,
        holidays={date(2026, 8, 10)},
    )
    assert result.due_date == date(2026, 8, 12)
    assert result.skipped_holidays == 1


def test_next_working_day_adjustment():
    result = calculate_deadline(
        date(2026, 8, 7),
        offset_days=1,
        day_basis=DayBasis.CALENDAR,
        adjustment=DeadlineAdjustment.NEXT_WORKING_DAY,
    )
    assert result.calculated_date == date(2026, 8, 8)
    assert result.due_date == date(2026, 8, 10)
    assert result.adjustment_days == 2


def test_zero_day_deadline_stays_on_trigger():
    result = calculate_deadline(date(2026, 8, 8), offset_days=0)
    assert result.due_date == date(2026, 8, 8)


def test_working_day_helper():
    assert is_working_day(date(2026, 8, 10))
    assert not is_working_day(date(2026, 8, 9))
