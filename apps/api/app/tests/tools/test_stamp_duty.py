from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.tools.stamp_duty.models import StampDutyCalculationRequest
from app.tools.stamp_duty.service import calculate_stamp_duty, list_rule_packs

client = TestClient(app)


def test_stamp_rule_packs_are_discoverable() -> None:
    ids = {pack.id for pack in list_rule_packs()}
    assert "demo-stamp-percentage-v1" in ids
    assert "demo-stamp-progressive-v1" in ids
    assert "demo-stamp-fixed-v1" in ids


def test_greater_of_consideration_or_market_is_used() -> None:
    result = calculate_stamp_duty(
        StampDutyCalculationRequest(
            rule_pack_id="demo-stamp-percentage-v1",
            instrument_date=date(2026, 8, 8),
            consideration_value=Decimal("1000000"),
            market_value=Decimal("1200000"),
        )
    )

    assert result.duty_base_value == Decimal("1200000.00")
    assert result.base_duty == Decimal("60000.00")
    assert result.mandatory_charge_total == Decimal("6000.00")
    assert result.final_duty == Decimal("66000.00")


def test_optional_fixed_charge_can_be_selected() -> None:
    result = calculate_stamp_duty(
        StampDutyCalculationRequest(
            rule_pack_id="demo-stamp-percentage-v1",
            instrument_date=date(2026, 8, 8),
            consideration_value=Decimal("10000"),
            market_value=Decimal("10000"),
            include_optional_charge_codes=["COPY"],
        )
    )

    # Base 500 + mandatory cess 50 + optional 100 = 650.
    assert result.base_duty == Decimal("500.00")
    assert result.optional_charge_total == Decimal("100.00")
    assert result.final_duty == Decimal("650.00")


def test_progressive_duty_calculation() -> None:
    result = calculate_stamp_duty(
        StampDutyCalculationRequest(
            rule_pack_id="demo-stamp-progressive-v1",
            instrument_date=date(2026, 8, 8),
            assessable_value=Decimal("600000"),
        )
    )

    # 100,000 @ 1% = 1,000
    # 400,000 @ 2% = 8,000
    # 100,000 @ 3% = 3,000
    assert result.base_duty == Decimal("12000.00")
    assert result.final_duty == Decimal("12000.00")
    assert len(result.breakdown) == 3


def test_progressive_maximum_cap_is_applied() -> None:
    result = calculate_stamp_duty(
        StampDutyCalculationRequest(
            rule_pack_id="demo-stamp-progressive-v1",
            instrument_date=date(2026, 8, 8),
            assessable_value=Decimal("5000000"),
        )
    )

    assert result.final_duty == Decimal("50000.00")
    assert any("Maximum total duty applied" in item for item in result.adjustments)


def test_fixed_duty_does_not_require_valuation_input() -> None:
    result = calculate_stamp_duty(
        StampDutyCalculationRequest(
            rule_pack_id="demo-stamp-fixed-v1",
            instrument_date=date(2026, 8, 8),
        )
    )

    assert result.duty_base_value is None
    assert result.base_duty == Decimal("100.00")
    assert result.final_duty == Decimal("100.00")


def test_missing_required_values_returns_422() -> None:
    response = client.post(
        "/api/v1/tools/stamp-duty/calculate",
        json={
            "rule_pack_id": "demo-stamp-percentage-v1",
            "instrument_date": "2026-08-08",
            "consideration_value": "100000"
        },
    )

    assert response.status_code == 422
    assert "market_value" in response.json()["detail"]


def test_unknown_optional_charge_returns_422() -> None:
    response = client.post(
        "/api/v1/tools/stamp-duty/calculate",
        json={
            "rule_pack_id": "demo-stamp-percentage-v1",
            "instrument_date": "2026-08-08",
            "consideration_value": "100000",
            "market_value": "100000",
            "include_optional_charge_codes": ["NOT-A-REAL-CODE"]
        },
    )

    assert response.status_code == 422
    assert "unknown optional charge" in response.json()["detail"]


def test_stamp_duty_rule_pack_list_endpoint() -> None:
    response = client.get("/api/v1/tools/stamp-duty/rule-packs")
    assert response.status_code == 200
    assert len(response.json()) >= 3
