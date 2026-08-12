from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.tools.limitation_period.models import (
    ExpiryAdjustment,
    LimitationExtension,
    LimitationPeriodRequest,
    PeriodUnit,
)
from app.tools.limitation_period.service import calculate_limitation_period

client = TestClient(app)


def test_three_year_period() -> None:
    request = LimitationPeriodRequest(
        trigger_date=date(2023, 8, 8),
        period_value=3,
        period_unit=PeriodUnit.YEARS,
    )

    result = calculate_limitation_period(request)

    assert result.base_expiry_date == date(2026, 8, 8)
    assert result.final_expiry_date == date(2026, 8, 8)


def test_leap_day_clamps_to_month_end() -> None:
    request = LimitationPeriodRequest(
        trigger_date=date(2024, 2, 29),
        period_value=1,
        period_unit=PeriodUnit.YEARS,
    )

    result = calculate_limitation_period(request)

    assert result.final_expiry_date == date(2025, 2, 28)


def test_month_end_clamps_for_shorter_month() -> None:
    request = LimitationPeriodRequest(
        trigger_date=date(2026, 1, 31),
        period_value=1,
        period_unit=PeriodUnit.MONTHS,
    )

    result = calculate_limitation_period(request)

    assert result.final_expiry_date == date(2026, 2, 28)


def test_extensions_are_added() -> None:
    request = LimitationPeriodRequest(
        trigger_date=date(2026, 1, 1),
        period_value=30,
        period_unit=PeriodUnit.DAYS,
        extension_periods=[
            LimitationExtension(days=5, reason="Example statutory exclusion"),
            LimitationExtension(days=2, reason="Example court-ordered extension"),
        ],
    )

    result = calculate_limitation_period(request)

    assert result.base_expiry_date == date(2026, 1, 31)
    assert result.total_extension_days == 7
    assert result.final_expiry_date == date(2026, 2, 7)


def test_rolls_forward_from_weekend_and_holiday() -> None:
    request = LimitationPeriodRequest(
        trigger_date=date(2026, 8, 3),
        period_value=12,
        period_unit=PeriodUnit.DAYS,
        expiry_adjustment=ExpiryAdjustment.NEXT_BUSINESS_DAY,
        excluded_dates=[date(2026, 8, 17)],
    )

    result = calculate_limitation_period(request)

    assert result.expiry_before_business_day_adjustment == date(2026, 8, 15)
    assert result.final_expiry_date == date(2026, 8, 18)
    assert result.expiry_adjustment is not None


def test_http_endpoint() -> None:
    response = client.post(
        "/api/v1/tools/limitation-periods/calculate",
        json={
            "trigger_date": "2023-08-08",
            "period_value": 3,
            "period_unit": "years",
            "extension_periods": [],
            "expiry_adjustment": "none",
        },
    )

    assert response.status_code == 200
    assert response.json()["final_expiry_date"] == "2026-08-08"
