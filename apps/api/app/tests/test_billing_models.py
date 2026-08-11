from decimal import Decimal

from app.models.billing import Invoice, InvoiceLine, InvoiceLineKind, InvoiceStatus
from app.services.billing.service import tax_review_findings


def _invoice(*, supplier_gstin=None, place_of_supply=None):
    invoice = Invoice(
        invoice_number="INV/2026/00001", client_name="Example Client", currency="INR",
        status=InvoiceStatus.DRAFT, supplier_gstin=supplier_gstin, place_of_supply=place_of_supply,
        subtotal=Decimal("1000"), discount_total=Decimal("0"), taxable_total=Decimal("1000"),
        cgst_total=Decimal("90"), sgst_total=Decimal("90"), igst_total=Decimal("0"), cess_total=Decimal("0"),
        tax_total=Decimal("180"), grand_total=Decimal("1180"), amount_paid=Decimal("0"), amount_due=Decimal("1180"),
    )
    invoice.lines = [InvoiceLine(kind=InvoiceLineKind.FEE, description="Professional services", quantity=Decimal("1"), unit_price=Decimal("1000"), discount_amount=Decimal("0"), taxable_amount=Decimal("1000"), cgst_rate=Decimal("9"), sgst_rate=Decimal("9"), igst_rate=Decimal("0"), cess_rate=Decimal("0"), cgst_amount=Decimal("90"), sgst_amount=Decimal("90"), igst_amount=Decimal("0"), cess_amount=Decimal("0"), line_total=Decimal("1180"), sort_order=0)]
    return invoice


def test_tax_review_flags_missing_supplier_gstin_and_place_of_supply():
    codes = {item["code"] for item in tax_review_findings(_invoice())}
    assert "supplier_gstin_missing" in codes
    assert "place_of_supply_missing" in codes


def test_tax_review_does_not_choose_tax_treatment_for_user():
    invoice = _invoice(supplier_gstin="29ABCDE1234F1Z5", place_of_supply="Karnataka")
    codes = {item["code"] for item in tax_review_findings(invoice)}
    assert "supplier_gstin_missing" not in codes
    assert "place_of_supply_missing" not in codes
    assert "service_code_missing" in codes
