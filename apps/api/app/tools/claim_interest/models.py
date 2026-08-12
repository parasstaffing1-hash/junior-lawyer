from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class InterestMethod(str, Enum):
    SIMPLE = "simple"
    COMPOUND = "compound"


class DayCountConvention(str, Enum):
    ACTUAL_365 = "actual_365"
    ACTUAL_366 = "actual_366"
    ACTUAL_360 = "actual_360"
    ACTUAL_ACTUAL = "actual_actual"
    THIRTY_360 = "30_360"


class CompoundingFrequency(str, Enum):
    ANNUAL = "annual"
    SEMIANNUAL = "semiannual"
    QUARTERLY = "quarterly"
    MONTHLY = "monthly"
    DAILY = "daily"


class PrincipalAdjustment(BaseModel):
    date: date
    amount: Decimal = Field(
        description=(
            "Change to outstanding principal. Use a negative amount for a payment/credit "
            "and a positive amount for an added principal amount."
        )
    )
    note: str | None = Field(default=None, max_length=300)


class ClaimInterestCalculationRequest(BaseModel):
    principal: Decimal = Field(gt=0)
    annual_rate_percent: Decimal = Field(ge=0, le=1000)
    start_date: date
    end_date: date
    method: InterestMethod = InterestMethod.SIMPLE
    day_count_convention: DayCountConvention = DayCountConvention.ACTUAL_365
    compounding_frequency: CompoundingFrequency = CompoundingFrequency.ANNUAL
    principal_adjustments: list[PrincipalAdjustment] = Field(default_factory=list)
    currency: str = Field(default="INR", min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_dates_and_adjustments(self) -> "ClaimInterestCalculationRequest":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be later than start_date")

        for adjustment in self.principal_adjustments:
            if adjustment.date <= self.start_date or adjustment.date >= self.end_date:
                raise ValueError(
                    "principal adjustment dates must fall strictly between start_date and end_date"
                )
        return self


class InterestBreakdownLine(BaseModel):
    period_start: date
    period_end: date
    days: int
    year_fraction: Decimal
    opening_principal: Decimal
    annual_rate_percent: Decimal
    method: InterestMethod
    interest: Decimal
    adjustment_at_period_end: Decimal = Decimal("0")
    closing_principal: Decimal
    note: str | None = None


class ClaimInterestCalculationResponse(BaseModel):
    currency: str
    principal: Decimal
    annual_rate_percent: Decimal
    start_date: date
    end_date: date
    method: InterestMethod
    day_count_convention: DayCountConvention
    compounding_frequency: CompoundingFrequency | None
    total_days: int
    total_adjustments: Decimal
    total_interest: Decimal
    final_principal: Decimal
    total_amount: Decimal
    breakdown: list[InterestBreakdownLine]
    disclaimer: str
