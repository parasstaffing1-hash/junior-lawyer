from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.billing import (
    ExpenseStatus, FeeArrangementStatus, FeeModel, InvoiceLineKind, InvoiceStatus,
    PaymentMethod, PaymentStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BillingProfileUpdate(BaseModel):
    legal_name: str | None = None
    billing_address: str | None = None
    city: str | None = None
    state: str | None = None
    state_code: str | None = None
    country: str = "India"
    gstin: str | None = Field(default=None, max_length=32)
    pan_last4: str | None = Field(default=None, min_length=4, max_length=4)
    email: str | None = None
    phone: str | None = None
    default_currency: str = "INR"
    invoice_prefix: str = Field(default="INV", min_length=1, max_length=40)
    default_payment_terms_days: int = Field(default=15, ge=0, le=365)
    bank_details: dict = Field(default_factory=dict)
    tax_configuration: dict = Field(default_factory=dict)


class BillingProfileRead(ORMModel):
    id: UUID
    organization_id: UUID
    legal_name: str | None
    billing_address: str | None
    city: str | None
    state: str | None
    state_code: str | None
    country: str
    gstin: str | None
    pan_last4: str | None
    email: str | None
    phone: str | None
    default_currency: str
    invoice_prefix: str
    next_invoice_sequence: int
    default_payment_terms_days: int
    bank_details_json: dict
    tax_configuration_json: dict


class RateCardCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    currency: str = "INR"
    is_default: bool = False
    notes: str | None = None


class RateCreate(BaseModel):
    membership_id: UUID | None = None
    role_label: str | None = None
    hourly_rate: Decimal = Field(gt=0)
    active_from: date | None = None
    active_to: date | None = None


class FeeArrangementCreate(BaseModel):
    client_id: UUID
    matter_id: UUID | None = None
    engagement_id: UUID | None = None
    rate_card_id: UUID | None = None
    name: str = Field(min_length=2, max_length=250)
    fee_model: FeeModel
    status: FeeArrangementStatus = FeeArrangementStatus.ACTIVE
    currency: str = "INR"
    default_hourly_rate: Decimal | None = Field(default=None, ge=0)
    fixed_fee: Decimal | None = Field(default=None, ge=0)
    retainer_amount: Decimal | None = Field(default=None, ge=0)
    fee_cap: Decimal | None = Field(default=None, ge=0)
    contingency_percent: Decimal | None = Field(default=None, ge=0, le=100)
    billing_frequency: str | None = None
    tax_treatment: dict = Field(default_factory=dict)
    notes: str | None = None


class FeeArrangementRead(ORMModel):
    id: UUID
    client_id: UUID
    matter_id: UUID | None
    engagement_id: UUID | None
    rate_card_id: UUID | None
    name: str
    fee_model: FeeModel
    status: FeeArrangementStatus
    currency: str
    default_hourly_rate: Decimal | None
    fixed_fee: Decimal | None
    retainer_amount: Decimal | None
    fee_cap: Decimal | None
    contingency_percent: Decimal | None
    billing_frequency: str | None
    tax_treatment_json: dict
    notes: str | None
    created_at: datetime


class ExpenseCreate(BaseModel):
    client_id: UUID | None = None
    matter_id: UUID | None = None
    expense_date: date
    description: str = Field(min_length=2, max_length=500)
    category: str | None = None
    amount: Decimal = Field(gt=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = "INR"
    billable: bool = True
    receipt_document_id: UUID | None = None
    notes: str | None = None


class ExpenseRead(ORMModel):
    id: UUID
    client_id: UUID | None
    matter_id: UUID | None
    expense_date: date
    description: str
    category: str | None
    amount: Decimal
    tax_amount: Decimal
    currency: str
    billable: bool
    status: ExpenseStatus
    receipt_document_id: UUID | None
    notes: str | None
    created_at: datetime


class InvoiceLineCreate(BaseModel):
    kind: InvoiceLineKind = InvoiceLineKind.FEE
    source_time_entry_id: UUID | None = None
    source_expense_id: UUID | None = None
    description: str = Field(min_length=1, max_length=1000)
    service_code: str | None = Field(default=None, max_length=32)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    cgst_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    sgst_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    igst_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    cess_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_gst_split(self):
        # The engine does not decide GST treatment. It only rejects obviously ambiguous
        # mixed intra/inter-state tax components on a single line.
        if self.igst_rate > 0 and (self.cgst_rate > 0 or self.sgst_rate > 0):
            raise ValueError("A line cannot simultaneously apply IGST and CGST/SGST")
        return self


class InvoiceCreate(BaseModel):
    client_id: UUID
    matter_id: UUID | None = None
    fee_arrangement_id: UUID | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str = "INR"
    client_address: str | None = None
    client_gstin: str | None = None
    client_state_code: str | None = None
    place_of_supply: str | None = None
    reverse_charge: bool = False
    notes: str | None = None
    metadata: dict = Field(default_factory=dict)
    lines: list[InvoiceLineCreate] = Field(default_factory=list)


class InvoiceLineRead(ORMModel):
    id: UUID
    kind: InvoiceLineKind
    source_time_entry_id: UUID | None
    source_expense_id: UUID | None
    description: str
    service_code: str | None
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    cgst_rate: Decimal
    sgst_rate: Decimal
    igst_rate: Decimal
    cess_rate: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    line_total: Decimal
    sort_order: int


class InvoiceRead(ORMModel):
    id: UUID
    client_id: UUID
    matter_id: UUID | None
    invoice_number: str
    status: InvoiceStatus
    issue_date: date | None
    due_date: date | None
    currency: str
    supplier_name: str | None
    supplier_address: str | None
    supplier_gstin: str | None
    supplier_state_code: str | None
    client_name: str
    client_address: str | None
    client_gstin: str | None
    client_state_code: str | None
    place_of_supply: str | None
    reverse_charge: bool
    subtotal: Decimal
    discount_total: Decimal
    taxable_total: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    cess_total: Decimal
    tax_total: Decimal
    grand_total: Decimal
    amount_paid: Decimal
    amount_due: Decimal
    tax_treatment_reviewed: bool
    reviewed_at: datetime | None
    issued_at: datetime | None
    irn: str | None
    acknowledgement_number: str | None
    notes: str | None
    lines: list[InvoiceLineRead] = Field(default_factory=list)
    created_at: datetime


class InvoiceReviewRequest(BaseModel):
    tax_treatment_reviewed: bool = True
    note: str | None = None


class InvoiceIssueRequest(BaseModel):
    irn: str | None = None
    acknowledgement_number: str | None = None
    acknowledgement_date: datetime | None = None


class PaymentCreate(BaseModel):
    client_id: UUID
    invoice_id: UUID | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "INR"
    payment_date: date
    method: PaymentMethod = PaymentMethod.BANK_TRANSFER
    status: PaymentStatus = PaymentStatus.CLEARED
    reference: str | None = None
    notes: str | None = None


class PaymentRead(ORMModel):
    id: UUID
    client_id: UUID
    invoice_id: UUID | None
    amount: Decimal
    currency: str
    payment_date: date
    method: PaymentMethod
    status: PaymentStatus
    reference: str | None
    notes: str | None
    created_at: datetime


class LedgerRow(BaseModel):
    id: UUID
    entry_date: date
    entry_type: str
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    currency: str
    invoice_id: UUID | None = None
    payment_id: UUID | None = None


class ClientStatement(BaseModel):
    client_id: UUID
    currency: str
    opening_balance: Decimal = Decimal("0.00")
    closing_balance: Decimal
    rows: list[LedgerRow]


class BillingOverview(BaseModel):
    draft_invoices: int
    issued_invoices: int
    overdue_invoices: int
    outstanding_amount: Decimal
    unbilled_minutes: int
    approved_expenses: Decimal
