from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.models.procedure import DayBasis, DeadlineAdjustment


@dataclass(frozen=True)
class DeadlineCalculation:
    trigger_date: date
    calculated_date: date
    due_date: date
    offset_days: int
    day_basis: DayBasis
    count_from_next_day: bool
    adjustment: DeadlineAdjustment
    skipped_weekends: int
    skipped_holidays: int
    adjustment_days: int

    def as_dict(self) -> dict:
        return {
            "trigger_date": self.trigger_date.isoformat(),
            "calculated_date": self.calculated_date.isoformat(),
            "due_date": self.due_date.isoformat(),
            "offset_days": self.offset_days,
            "day_basis": self.day_basis.value,
            "count_from_next_day": self.count_from_next_day,
            "adjustment": self.adjustment.value,
            "skipped_weekends": self.skipped_weekends,
            "skipped_holidays": self.skipped_holidays,
            "adjustment_days": self.adjustment_days,
        }


def is_working_day(value: date, holidays: set[date] | None = None) -> bool:
    holidays = holidays or set()
    return value.weekday() < 5 and value not in holidays


def _adjust(value: date, adjustment: DeadlineAdjustment, holidays: set[date]) -> tuple[date, int]:
    if adjustment == DeadlineAdjustment.NONE or is_working_day(value, holidays):
        return value, 0
    direction = 1 if adjustment == DeadlineAdjustment.NEXT_WORKING_DAY else -1
    adjusted = value
    moved = 0
    while not is_working_day(adjusted, holidays):
        adjusted += timedelta(days=direction)
        moved += direction
    return adjusted, moved


def calculate_deadline(
    trigger_date: date,
    *,
    offset_days: int,
    day_basis: DayBasis = DayBasis.CALENDAR,
    count_from_next_day: bool = True,
    adjustment: DeadlineAdjustment = DeadlineAdjustment.NONE,
    holidays: set[date] | None = None,
) -> DeadlineCalculation:
    if offset_days < 0:
        raise ValueError("offset_days must be zero or positive")
    holidays = holidays or set()
    skipped_weekends = 0
    skipped_holidays = 0

    if day_basis == DayBasis.CALENDAR:
        start = trigger_date + (timedelta(days=1) if count_from_next_day else timedelta())
        calculated = start + timedelta(days=max(offset_days - 1, 0)) if offset_days else trigger_date
    else:
        cursor = trigger_date
        counted = 0
        if not count_from_next_day and offset_days > 0 and is_working_day(cursor, holidays):
            counted = 1
        while counted < offset_days:
            cursor += timedelta(days=1)
            if cursor.weekday() >= 5:
                skipped_weekends += 1
                continue
            if cursor in holidays:
                skipped_holidays += 1
                continue
            counted += 1
        calculated = cursor if offset_days else trigger_date

    due, adjustment_days = _adjust(calculated, adjustment, holidays)
    return DeadlineCalculation(
        trigger_date=trigger_date,
        calculated_date=calculated,
        due_date=due,
        offset_days=offset_days,
        day_basis=day_basis,
        count_from_next_day=count_from_next_day,
        adjustment=adjustment,
        skipped_weekends=skipped_weekends,
        skipped_holidays=skipped_holidays,
        adjustment_days=adjustment_days,
    )
