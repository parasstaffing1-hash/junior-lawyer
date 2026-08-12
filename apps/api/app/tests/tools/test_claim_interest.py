from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tools.claim_interest.models import (
    ClaimInterestCalculationRequest,
    CompoundingFrequency,
    DayCountConvention,
    InterestMethod,
    PrincipalAdjustment,
)
from app.tools.claim_interest.service import ClaimInterestInputError, calculate_claim_interest


def test_simple_interest_actual_365_one_year() -> None:
    result = calculate_claim_interest(
        ClaimInterestCalculationRequest(
            principal=Decimal("100000"),
            annual_rate_percent=Decimal("10"),
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
            method=InterestMethod.SIMPLE,
            day_count_convention=DayCountConvention.ACTUAL_365,
        )
    )
    assert result.total_interest == Decimal("10000.00")
    assert result.total_amount == Decimal("110000.00")


def test_simple_interest_with_partial_payment() -> None:
    result = calculate_claim_interest(
        ClaimInterestCalculationRequest(
            principal=Decimal("100000"),
            annual_rate_percent=Decimal("10"),
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
            method=InterestMethod.SIMPLE,
            day_count_convention=DayCountConvention.ACTUAL_365,
            principal_adjustments=[
                PrincipalAdjustment(
                    date=date(2025, 7, 2),
                    amount=Decimal("-40000"),
                    note="Partial payment",
                )
            ],
        )
    )
    assert result.final_principal == Decimal("60000.00")
    assert result.total_adjustments == Decimal("-40000.00")
    assert len(result.breakdown) == 2
    assert Decimal("7900") < result.total_interest < Decimal("8100")


def test_compound_annual_one_year() -> None:
    result = calculate_claim_interest(
        ClaimInterestCalculationRequest(
            principal=Decimal("100000"),
            annual_rate_percent=Decimal("10"),
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
            method=InterestMethod.COMPOUND,
            day_count_convention=DayCountConvention.ACTUAL_365,
            compounding_frequency=CompoundingFrequency.ANNUAL,
        )
    )
    assert result.total_interest == Decimal("10000.00")
    assert result.total_amount == Decimal("110000.00")
    assert result.final_principal == Decimal("110000.00")


def test_actual_actual_handles_leap_year() -> None:
    result = calculate_claim_interest(
        ClaimInterestCalculationRequest(
            principal=Decimal("36600"),
            annual_rate_percent=Decimal("10"),
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
            method=InterestMethod.SIMPLE,
            day_count_convention=DayCountConvention.ACTUAL_ACTUAL,
        )
    )
    assert result.total_interest == Decimal("3660.00")


def test_thirty_360_one_year() -> None:
    result = calculate_claim_interest(
        ClaimInterestCalculationRequest(
            principal=Decimal("12000"),
            annual_rate_percent=Decimal("12"),
            start_date=date(2025, 2, 15),
            end_date=date(2026, 2, 15),
            method=InterestMethod.SIMPLE,
            day_count_convention=DayCountConvention.THIRTY_360,
        )
    )
    assert result.total_interest == Decimal("1440.00")


def test_adjustment_cannot_reduce_principal_below_zero() -> None:
    with pytest.raises(ClaimInterestInputError):
        calculate_claim_interest(
            ClaimInterestCalculationRequest(
                principal=Decimal("1000"),
                annual_rate_percent=Decimal("10"),
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
                principal_adjustments=[
                    PrincipalAdjustment(date=date(2025, 6, 1), amount=Decimal("-2000"))
                ],
            )
        )


def test_api_calculates_interest() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/tools/claim-interest/calculate",
        json={
            "principal": "100000",
            "annual_rate_percent": "10",
            "start_date": "2025-01-01",
            "end_date": "2026-01-01",
            "method": "simple",
            "day_count_convention": "actual_365",
            "currency": "INR",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_interest"] == "10000.00"
    assert body["total_amount"] == "110000.00"
