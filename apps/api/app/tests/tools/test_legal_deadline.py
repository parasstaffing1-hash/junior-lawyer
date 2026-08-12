from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.tools.legal_deadline.models import CountMode, LegalDeadlineRequest
from app.tools.legal_deadline.service import calculate_deadline

client = TestClient(app)


def test_five_business_days_skips_weekend() -> None:
    request = LegalDeadlineRequest(
        start_date=date(2026, 8, 3),  # Monday
        days=5,
        count_mode=CountMode.BUSINESS_DAYS,
    )

    result = calculate_deadline(request)

    assert result.due_date == date(2026, 8, 10)


def test_business_days_respect_excluded_date() -> None:
    request = LegalDeadlineRequest(
        start_date=date(2026, 8, 3),
        days=5,
        count_mode=CountMode.BUSINESS_DAYS,
        excluded_dates=[date(2026, 8, 7)],
    )

    result = calculate_deadline(request)

    assert result.due_date == date(2026, 8, 11)


def test_calendar_deadline_rolls_from_weekend() -> None:
    request = LegalDeadlineRequest(
        start_date=date(2026, 8, 3),
        days=12,  # Saturday, 15 Aug 2026
        count_mode=CountMode.CALENDAR_DAYS,
        roll_if_non_business=True,
    )

    result = calculate_deadline(request)

    assert result.due_date == date(2026, 8, 17)
    assert result.adjustment is not None
    assert result.adjustment.original_date == date(2026, 8, 15)


def test_include_start_date_for_business_count() -> None:
    request = LegalDeadlineRequest(
        start_date=date(2026, 8, 3),
        days=1,
        count_mode=CountMode.BUSINESS_DAYS,
        include_start_date=True,
    )

    result = calculate_deadline(request)

    assert result.due_date == date(2026, 8, 3)


def test_http_endpoint() -> None:
    response = client.post(
        "/api/v1/tools/legal-deadlines/calculate",
        json={
            "start_date": "2026-08-03",
            "days": 5,
            "count_mode": "business_days",
            "excluded_dates": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["due_date"] == "2026-08-10"
