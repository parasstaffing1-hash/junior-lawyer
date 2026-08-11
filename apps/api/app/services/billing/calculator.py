from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping, Any


TWOPLACES = Decimal("0.01")
HUNDRED = Decimal("100")


def money(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def rate(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class LineTotals:
    gross: Decimal
    discount: Decimal
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    cess: Decimal
    tax: Decimal
    total: Decimal


@dataclass(frozen=True, slots=True)
class InvoiceTotals:
    subtotal: Decimal
    discount_total: Decimal
    taxable_total: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    cess_total: Decimal
    tax_total: Decimal
    grand_total: Decimal


def calculate_line(
    *, quantity: Decimal, unit_price: Decimal, discount_amount: Decimal = Decimal("0"),
    cgst_rate: Decimal = Decimal("0"), sgst_rate: Decimal = Decimal("0"),
    igst_rate: Decimal = Decimal("0"), cess_rate: Decimal = Decimal("0"),
) -> LineTotals:
    q = Decimal(str(quantity))
    unit = money(unit_price)
    gross = money(q * unit)
    discount = money(discount_amount)
    if discount > gross:
        raise ValueError("Discount cannot exceed gross line amount")
    taxable = money(gross - discount)
    cgst = money(taxable * rate(cgst_rate) / HUNDRED)
    sgst = money(taxable * rate(sgst_rate) / HUNDRED)
    igst = money(taxable * rate(igst_rate) / HUNDRED)
    cess = money(taxable * rate(cess_rate) / HUNDRED)
    tax = money(cgst + sgst + igst + cess)
    return LineTotals(gross, discount, taxable, cgst, sgst, igst, cess, tax, money(taxable + tax))


def aggregate_lines(lines: Iterable[LineTotals]) -> InvoiceTotals:
    rows = list(lines)
    return InvoiceTotals(
        subtotal=money(sum((r.gross for r in rows), Decimal("0"))),
        discount_total=money(sum((r.discount for r in rows), Decimal("0"))),
        taxable_total=money(sum((r.taxable for r in rows), Decimal("0"))),
        cgst_total=money(sum((r.cgst for r in rows), Decimal("0"))),
        sgst_total=money(sum((r.sgst for r in rows), Decimal("0"))),
        igst_total=money(sum((r.igst for r in rows), Decimal("0"))),
        cess_total=money(sum((r.cess for r in rows), Decimal("0"))),
        tax_total=money(sum((r.tax for r in rows), Decimal("0"))),
        grand_total=money(sum((r.total for r in rows), Decimal("0"))),
    )


def stable_hash(payload: Mapping[str, Any]) -> str:
    def default(value):
        if isinstance(value, Decimal): return str(value)
        return str(value)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=default).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
