from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.tools.court_fee.models import CourtFeeCalculationRequest
from app.tools.court_fee.service import calculate_court_fee, list_rule_packs

client = TestClient(app)


def test_rule_packs_are_discoverable() -> None:
    ids = {pack.id for pack in list_rule_packs()}
    assert "demo-progressive-v1" in ids
    assert "demo-fixed-v1" in ids


def test_progressive_fee_calculation() -> None:
    result = calculate_court_fee(
        CourtFeeCalculationRequest(
            rule_pack_id="demo-progressive-v1",
            filing_date=date(2026, 8, 8),
            claim_value=Decimal("600000"),
        )
    )

    # 100,000 @ 2% = 2,000
    # 400,000 @ 1% = 4,000
    # 100,000 @ 0.5% = 500
    assert result.base_fee == Decimal("6500.00")
    assert result.final_fee == Decimal("6500.00")
    assert len(result.breakdown) == 3


def test_additional_fees_are_opt_in() -> None:
    result = calculate_court_fee(
        CourtFeeCalculationRequest(
            rule_pack_id="demo-fixed-v1",
            filing_date=date(2026, 8, 8),
            include_additional_fee_codes=["PROCESS"],
        )
    )

    assert result.base_fee == Decimal("750.00")
    assert result.additional_fee_total == Decimal("100.00")
    assert result.final_fee == Decimal("850.00")


def test_minimum_fee_is_applied() -> None:
    result = calculate_court_fee(
        CourtFeeCalculationRequest(
            rule_pack_id="demo-progressive-v1",
            filing_date=date(2026, 8, 8),
            claim_value=Decimal("100"),
        )
    )

    assert result.subtotal_before_limits == Decimal("2.00")
    assert result.final_fee == Decimal("500.00")
    assert any("Minimum fee applied" in item for item in result.adjustments)


def test_maximum_fee_is_applied() -> None:
    result = calculate_court_fee(
        CourtFeeCalculationRequest(
            rule_pack_id="demo-progressive-v1",
            filing_date=date(2026, 8, 8),
            claim_value=Decimal("10000000"),
        )
    )

    assert result.final_fee == Decimal("25000.00")
    assert any("Maximum fee applied" in item for item in result.adjustments)


def test_unknown_rule_pack_returns_404() -> None:
    response = client.post(
        "/api/v1/tools/court-fees/calculate",
        json={
            "rule_pack_id": "does-not-exist",
            "filing_date": "2026-08-08"
        },
    )

    assert response.status_code == 404


def test_progressive_pack_requires_claim_value() -> None:
    response = client.post(
        "/api/v1/tools/court-fees/calculate",
        json={
            "rule_pack_id": "demo-progressive-v1",
            "filing_date": "2026-08-08"
        },
    )

    assert response.status_code == 422
    assert "claim_value is required" in response.json()["detail"]


def test_rule_pack_list_endpoint() -> None:
    response = client.get("/api/v1/tools/court-fees/rule-packs")
    assert response.status_code == 200
    assert len(response.json()) >= 2
