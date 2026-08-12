from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class CountMode(str, Enum):
    CALENDAR_DAYS = "calendar_days"
    BUSINESS_DAYS = "business_days"


class LegalDeadlineRequest(BaseModel):
    start_date: date
    days: int = Field(ge=0, le=3650)
    count_mode: CountMode = CountMode.CALENDAR_DAYS
    include_start_date: bool = False
    roll_if_non_business: bool = True
    excluded_dates: list[date] = Field(default_factory=list)
    weekend_weekdays: set[int] = Field(default_factory=lambda: {5, 6})

    @model_validator(mode="after")
    def validate_weekend_weekdays(self) -> "LegalDeadlineRequest":
        if any(day < 0 or day > 6 for day in self.weekend_weekdays):
            raise ValueError("weekend_weekdays must contain integers from 0 to 6")
        return self


class DeadlineAdjustment(BaseModel):
    original_date: date
    adjusted_date: date
    reason: str


class LegalDeadlineResponse(BaseModel):
    start_date: date
    due_date: date
    days: int
    count_mode: CountMode
    include_start_date: bool
    excluded_dates_used: list[date]
    adjustment: DeadlineAdjustment | None = None
    disclaimer: str
