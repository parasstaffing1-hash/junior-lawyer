from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class PeriodUnit(str, Enum):
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


class ExpiryAdjustment(str, Enum):
    NONE = "none"
    NEXT_BUSINESS_DAY = "next_business_day"


class LimitationExtension(BaseModel):
    days: int = Field(ge=0, le=3650)
    reason: str | None = Field(default=None, max_length=300)


class LimitationPeriodRequest(BaseModel):
    trigger_date: date
    period_value: int = Field(gt=0, le=12000)
    period_unit: PeriodUnit
    extension_periods: list[LimitationExtension] = Field(default_factory=list)
    expiry_adjustment: ExpiryAdjustment = ExpiryAdjustment.NONE
    excluded_dates: list[date] = Field(default_factory=list)
    weekend_weekdays: set[int] = Field(default_factory=lambda: {5, 6})

    @model_validator(mode="after")
    def validate_weekend_weekdays(self) -> "LimitationPeriodRequest":
        if any(day < 0 or day > 6 for day in self.weekend_weekdays):
            raise ValueError("weekend_weekdays must contain integers from 0 to 6")
        return self


class ExpiryAdjustmentResult(BaseModel):
    original_date: date
    adjusted_date: date
    reason: str


class LimitationPeriodResponse(BaseModel):
    trigger_date: date
    period_value: int
    period_unit: PeriodUnit
    base_expiry_date: date
    total_extension_days: int
    expiry_before_business_day_adjustment: date
    final_expiry_date: date
    expiry_adjustment: ExpiryAdjustmentResult | None = None
    excluded_dates_used: list[date]
    calculation_notes: list[str]
    disclaimer: str
