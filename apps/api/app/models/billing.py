from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


MONEY = Numeric(16, 2)
RATE = Numeric(8, 4)
QTY = Numeric(12, 4)


class FeeModel(StrEnum):
    HOURLY = "hourly"
    FIXED = "fixed"
    RETAINER = "retainer"
    CAPPED = "capped"
    CONTINGENCY = "contingency"
    CUSTOM = "custom"


class FeeArrangementStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class ExpenseStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    BILLED = "billed"
    REJECTED = "rejected"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    VOID = "void"


class InvoiceLineKind(StrEnum):
    TIME = "time"
    EXPENSE = "expense"
    FEE = "fee"
    ADJUSTMENT = "adjustment"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    CLEARED = "cleared"
    FAILED = "failed"
    REVERSED = "reversed"


class PaymentMethod(StrEnum):
    BANK_TRANSFER = "bank_transfer"
    UPI = "upi"
    CHEQUE = "cheque"
    CASH = "cash"
    CARD = "card"
    OTHER = "other"


class LedgerEntryType(StrEnum):
    INVOICE = "invoice"
    PAYMENT = "payment"
    CREDIT = "credit"
    ADJUSTMENT = "adjustment"


class OrganizationBillingProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organization_billing_profiles"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_org_billing_profile_org"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(300))
    billing_address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    state_code: Mapped[str | None] = mapped_column(String(10))
    country: Mapped[str] = mapped_column(String(120), default="India")
    gstin: Mapped[str | None] = mapped_column(String(32), index=True)
    pan_last4: Mapped[str | None] = mapped_column(String(4))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(64))
    default_currency: Mapped[str] = mapped_column(String(8), default="INR")
    invoice_prefix: Mapped[str] = mapped_column(String(40), default="INV")
    next_invoice_sequence: Mapped[int] = mapped_column(Integer, default=1)
    default_payment_terms_days: Mapped[int] = mapped_column(Integer, default=15)
    bank_details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    tax_configuration_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BillingRateCard(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "billing_rate_cards"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class BillingRate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "billing_rates"

    rate_card_id: Mapped[UUID] = mapped_column(ForeignKey("billing_rate_cards.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), nullable=True, index=True)
    role_label: Mapped[str | None] = mapped_column(String(120), index=True)
    hourly_rate: Mapped[Decimal] = mapped_column(MONEY)
    active_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    active_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class FeeArrangement(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "fee_arrangements"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True)
    engagement_id: Mapped[UUID | None] = mapped_column(ForeignKey("engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    rate_card_id: Mapped[UUID | None] = mapped_column(ForeignKey("billing_rate_cards.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(250))
    fee_model: Mapped[FeeModel] = mapped_column(Enum(FeeModel, native_enum=False), index=True)
    status: Mapped[FeeArrangementStatus] = mapped_column(Enum(FeeArrangementStatus, native_enum=False), default=FeeArrangementStatus.DRAFT, index=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    default_hourly_rate: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    fixed_fee: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    retainer_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    fee_cap: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    contingency_percent: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    billing_frequency: Mapped[str | None] = mapped_column(String(60))
    tax_treatment_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)


class Expense(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "billing_expenses"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    incurred_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    billable: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    status: Mapped[ExpenseStatus] = mapped_column(Enum(ExpenseStatus, native_enum=False), default=ExpenseStatus.DRAFT, index=True)
    receipt_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Invoice(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("organization_id", "invoice_number", name="uq_invoice_org_number"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_arrangement_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_arrangements.id", ondelete="SET NULL"), nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus, native_enum=False), default=InvoiceStatus.DRAFT, index=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    supplier_name: Mapped[str | None] = mapped_column(String(300))
    supplier_address: Mapped[str | None] = mapped_column(Text)
    supplier_gstin: Mapped[str | None] = mapped_column(String(32))
    supplier_state_code: Mapped[str | None] = mapped_column(String(10))
    supplier_email: Mapped[str | None] = mapped_column(String(320))

    client_name: Mapped[str] = mapped_column(String(300))
    client_address: Mapped[str | None] = mapped_column(Text)
    client_gstin: Mapped[str | None] = mapped_column(String(32))
    client_state_code: Mapped[str | None] = mapped_column(String(10))
    place_of_supply: Mapped[str | None] = mapped_column(String(160))
    reverse_charge: Mapped[bool] = mapped_column(Boolean, default=False)

    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    discount_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    taxable_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    cgst_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    sgst_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    igst_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    cess_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    grand_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    amount_paid: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    amount_due: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))

    tax_treatment_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    irn: Mapped[str | None] = mapped_column(String(128), index=True)
    acknowledgement_number: Mapped[str | None] = mapped_column(String(128))
    acknowledgement_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    lines = relationship("InvoiceLine", cascade="all, delete-orphan", lazy="selectin", order_by="InvoiceLine.sort_order")


class InvoiceLine(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    kind: Mapped[InvoiceLineKind] = mapped_column(Enum(InvoiceLineKind, native_enum=False), default=InvoiceLineKind.FEE, index=True)
    source_time_entry_id: Mapped[UUID | None] = mapped_column(ForeignKey("time_entries.id", ondelete="SET NULL"), nullable=True, index=True)
    source_expense_id: Mapped[UUID | None] = mapped_column(ForeignKey("billing_expenses.id", ondelete="SET NULL"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(1000))
    service_code: Mapped[str | None] = mapped_column(String(32), index=True)
    quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    discount_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    taxable_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    cgst_rate: Mapped[Decimal] = mapped_column(RATE, default=Decimal("0"))
    sgst_rate: Mapped[Decimal] = mapped_column(RATE, default=Decimal("0"))
    igst_rate: Mapped[Decimal] = mapped_column(RATE, default=Decimal("0"))
    cess_rate: Mapped[Decimal] = mapped_column(RATE, default=Decimal("0"))
    cgst_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    sgst_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    igst_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    cess_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class InvoiceVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "invoice_versions"
    __table_args__ = (UniqueConstraint("invoice_id", "version_number", name="uq_invoice_version_number"),)

    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)


class Payment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payments"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), index=True)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    payment_date: Mapped[date] = mapped_column(Date, index=True)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, native_enum=False), default=PaymentMethod.BANK_TRANSFER, index=True)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, native_enum=False), default=PaymentStatus.CLEARED, index=True)
    reference: Mapped[str | None] = mapped_column(String(200), index=True)
    recorded_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)


class ClientLedgerEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_ledger_entries"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_id: Mapped[UUID | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    entry_type: Mapped[LedgerEntryType] = mapped_column(Enum(LedgerEntryType, native_enum=False), index=True)
    debit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    credit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    description: Mapped[str] = mapped_column(String(500))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
