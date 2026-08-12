from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.tools.key_dates_obligations.models import (
    DateKind,
    ExtractOptions,
    ExtractRequest,
    Frequency,
    ObligationType,
)
from app.tools.key_dates_obligations.service import extract_key_dates_and_obligations

client = TestClient(app)


SAMPLE = """This Agreement is effective on 8 August 2026 and expires on August 7, 2027.
The Customer shall pay each invoice within 30 days after receipt of the invoice.
The Supplier must maintain insurance coverage throughout the term.
The Customer shall provide written notice at least 60 days before expiry.
The Supplier shall submit a compliance report quarterly.
"""


def test_extracts_absolute_dates() -> None:
    result = extract_key_dates_and_obligations(ExtractRequest(text=SAMPLE))
    absolute = [item for item in result.dates if item.normalized_date]
    assert {item.normalized_date for item in absolute} == {date(2026, 8, 8), date(2027, 8, 7)}


def test_classifies_effective_and_expiry() -> None:
    result = extract_key_dates_and_obligations(ExtractRequest(text=SAMPLE))
    kinds = {item.date_kind for item in result.dates}
    assert DateKind.EFFECTIVE in kinds
    assert DateKind.EXPIRY in kinds


def test_extracts_relative_payment_deadline() -> None:
    result = extract_key_dates_and_obligations(ExtractRequest(text=SAMPLE))
    item = next(item for item in result.dates if item.date_kind == DateKind.PAYMENT_DUE and item.relative_value)
    assert item.relative_value == 30
    assert item.relative_unit.value == "days"
    assert item.anchor.lower().startswith("receipt")


def test_extracts_business_day_relative_deadline() -> None:
    text = "The Buyer shall pay the amount 10 business days after receipt of a valid invoice."
    result = extract_key_dates_and_obligations(ExtractRequest(text=text))
    item = next(item for item in result.dates if item.relative_value)
    assert item.relative_value == 10
    assert item.relative_unit.value == "business_days"


def test_obligation_actor_action_and_type() -> None:
    result = extract_key_dates_and_obligations(ExtractRequest(text=SAMPLE))
    payment = next(item for item in result.obligations if item.obligation_type == ObligationType.PAYMENT)
    assert payment.actor == "The Customer"
    assert payment.action.startswith("pay each invoice")
    assert payment.deadline_expression is not None


def test_detects_quarterly_frequency() -> None:
    result = extract_key_dates_and_obligations(ExtractRequest(text=SAMPLE))
    reporting = next(item for item in result.obligations if item.obligation_type == ObligationType.REPORTING)
    assert reporting.frequency == Frequency.QUARTERLY


def test_detects_continuous_insurance_obligation() -> None:
    result = extract_key_dates_and_obligations(ExtractRequest(text=SAMPLE))
    insurance = next(item for item in result.obligations if item.obligation_type == ObligationType.INSURANCE)
    assert insurance.frequency == Frequency.CONTINUOUS


def test_exact_offsets_for_obligation() -> None:
    result = extract_key_dates_and_obligations(ExtractRequest(text=SAMPLE))
    item = result.obligations[0]
    normalized = SAMPLE.replace("\r\n", "\n").replace("\r", "\n")
    assert normalized[item.start:item.end] == item.text
    assert item.line >= 1
    assert item.column >= 1


def test_filters_date_and_obligation_types() -> None:
    result = extract_key_dates_and_obligations(
        ExtractRequest(
            text=SAMPLE,
            options=ExtractOptions(
                date_kinds=[DateKind.NOTICE_DEADLINE],
                obligation_types=[ObligationType.NOTICE],
            ),
        )
    )
    assert result.dates
    assert all(item.date_kind == DateKind.NOTICE_DEADLINE for item in result.dates)
    assert len(result.obligations) == 1
    assert result.obligations[0].obligation_type == ObligationType.NOTICE


def test_other_dates_are_excluded_by_default() -> None:
    result = extract_key_dates_and_obligations(ExtractRequest(text="Meeting held on 2026-08-08."))
    assert result.dates == []
    result2 = extract_key_dates_and_obligations(
        ExtractRequest(text="Meeting held on 2026-08-08.", options=ExtractOptions(include_other_dates=True))
    )
    assert len(result2.dates) == 1
    assert result2.dates[0].date_kind == DateKind.OTHER


def test_api_extract_and_patterns() -> None:
    patterns = client.get("/api/v1/tools/key-dates-obligations/patterns")
    assert patterns.status_code == 200
    assert "YYYY-MM-DD" in patterns.json()["absolute_date_formats"]
    response = client.post("/api/v1/tools/key-dates-obligations/extract", json={"text": SAMPLE})
    assert response.status_code == 200
    assert response.json()["summary"]["obligations_returned"] >= 4


def test_invalid_calendar_date_is_warned_not_returned() -> None:
    text = "The Agreement expires on 31 February 2027."
    result = extract_key_dates_and_obligations(ExtractRequest(text=text))
    assert result.dates == []
    assert any("invalid calendar date" in warning.lower() for warning in result.warnings)
