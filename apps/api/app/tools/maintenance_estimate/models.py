from __future__ import annotations

from pydantic import BaseModel, Field


class MaintenanceEstimateRequest(BaseModel):
    """Monthly figures, in rupees."""

    respondent_monthly_income: float = Field(ge=0)
    # Statutory deductions only. Loan EMIs and discretionary spending are not
    # deducted, because courts routinely decline to.
    statutory_deductions: float = Field(default=0, ge=0)
    applicant_monthly_income: float = Field(default=0, ge=0)
    dependants: int = Field(default=1, ge=1, le=12)
    minor_children: int = Field(default=0, ge=0, le=12)
    respondent_has_other_dependants: bool = False


class MaintenanceBand(BaseModel):
    label_en: str
    label_hi: str
    monthly_amount: float
    share_of_net_income: float
    reasoning_en: str


class MaintenanceEstimateResponse(BaseModel):
    net_monthly_income: float
    bands: list[MaintenanceBand]
    factors_en: list[str]
    disclaimer_en: str
    disclaimer_hi: str
