from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.billing import InvoiceLineCreate
from app.services.billing.calculator import aggregate_lines, calculate_line, money, stable_hash


def test_money_rounds_half_up_to_paise():
    assert money("10.005") == Decimal("10.01")
    assert money("10.004") == Decimal("10.00")


def test_line_math_without_tax():
    row = calculate_line(quantity=Decimal("2.5"), unit_price=Decimal("1000"), discount_amount=Decimal("250"))
    assert row.gross == Decimal("2500.00")
    assert row.taxable == Decimal("2250.00")
    assert row.tax == Decimal("0.00")
    assert row.total == Decimal("2250.00")


def test_line_math_cgst_sgst_is_deterministic():
    row = calculate_line(quantity=Decimal("1"), unit_price=Decimal("1000"), cgst_rate=Decimal("9"), sgst_rate=Decimal("9"))
    assert row.cgst == Decimal("90.00")
    assert row.sgst == Decimal("90.00")
    assert row.igst == Decimal("0.00")
    assert row.total == Decimal("1180.00")


def test_line_math_igst():
    row = calculate_line(quantity=Decimal("1"), unit_price=Decimal("2500"), igst_rate=Decimal("18"))
    assert row.igst == Decimal("450.00")
    assert row.total == Decimal("2950.00")


def test_discount_cannot_exceed_gross():
    with pytest.raises(ValueError):
        calculate_line(quantity=Decimal("1"), unit_price=Decimal("100"), discount_amount=Decimal("101"))


def test_schema_rejects_mixed_igst_and_cgst_sgst_components():
    with pytest.raises(ValidationError):
        InvoiceLineCreate(description="Legal services", unit_price=1000, cgst_rate=9, sgst_rate=9, igst_rate=18)


def test_invoice_totals_aggregate_component_wise():
    lines = [
        calculate_line(quantity=1, unit_price=1000, cgst_rate=9, sgst_rate=9),
        calculate_line(quantity=2, unit_price=500, discount_amount=100, cgst_rate=9, sgst_rate=9),
    ]
    totals = aggregate_lines(lines)
    assert totals.subtotal == Decimal("2000.00")
    assert totals.discount_total == Decimal("100.00")
    assert totals.taxable_total == Decimal("1900.00")
    assert totals.tax_total == Decimal("342.00")
    assert totals.grand_total == Decimal("2242.00")


def test_stable_hash_is_key_order_independent():
    assert stable_hash({"b": 2, "a": 1}) == stable_hash({"a": 1, "b": 2})
