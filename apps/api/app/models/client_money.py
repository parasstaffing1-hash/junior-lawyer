from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin

MONEY = Numeric(16, 2)


class ClientMoneyAccountStatus(StrEnum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


class JournalEntryType(StrEnum):
    DEPOSIT = "deposit"
    REFUND = "refund"
    DISBURSEMENT = "disbursement"
    FEE_TRANSFER = "fee_transfer"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"


class JournalEntryStatus(StrEnum):
    POSTED = "posted"
    REVERSED = "reversed"


class ClientMoneyLedgerAccount(StrEnum):
    BANK_CONTROL = "bank_control"
    CLIENT_LIABILITY = "client_liability"
    FEE_TRANSFER_CLEARING = "fee_transfer_clearing"
    ADJUSTMENT_CLEARING = "adjustment_clearing"


class TransferRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class ReconciliationStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    LOCKED = "locked"


class ReconciliationItemStatus(StrEnum):
    UNMATCHED = "unmatched"
    MATCHED = "matched"
    EXCLUDED = "excluded"


class PaymentProviderKind(StrEnum):
    MANUAL = "manual"
    MOCK = "mock"
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    OTHER = "other"


class PaymentIntentStatus(StrEnum):
    CREATED = "created"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ClientMoneyAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_money_accounts"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_client_money_account_org_name"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[ClientMoneyAccountStatus] = mapped_column(Enum(ClientMoneyAccountStatus, native_enum=False), default=ClientMoneyAccountStatus.ACTIVE, index=True)
    bank_name: Mapped[str | None] = mapped_column(String(220))
    bank_account_last4: Mapped[str | None] = mapped_column(String(4))
    bank_reference: Mapped[str | None] = mapped_column(String(120))
    require_separate_approver: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ClientMoneyJournalEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_money_journal_entries"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("client_money_accounts.id", ondelete="RESTRICT"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    entry_type: Mapped[JournalEntryType] = mapped_column(Enum(JournalEntryType, native_enum=False), index=True)
    status: Mapped[JournalEntryStatus] = mapped_column(Enum(JournalEntryStatus, native_enum=False), default=JournalEntryStatus.POSTED, index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    reference: Mapped[str | None] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(String(500))
    transfer_request_id: Mapped[UUID | None] = mapped_column(ForeignKey("client_money_transfer_requests.id", ondelete="SET NULL", use_alter=True), nullable=True, index=True)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    reverses_entry_id: Mapped[UUID | None] = mapped_column(ForeignKey("client_money_journal_entries.id", ondelete="SET NULL"), nullable=True, index=True)
    posted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    reversed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ClientMoneyJournalLine(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_money_journal_lines"

    journal_entry_id: Mapped[UUID] = mapped_column(ForeignKey("client_money_journal_entries.id", ondelete="CASCADE"), index=True)
    ledger_account: Mapped[ClientMoneyLedgerAccount] = mapped_column(Enum(ClientMoneyLedgerAccount, native_enum=False), index=True)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    debit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    credit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    memo: Mapped[str | None] = mapped_column(String(500))


class ClientMoneyTransferRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_money_transfer_requests"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("client_money_accounts.id", ondelete="RESTRICT"), index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[TransferRequestStatus] = mapped_column(Enum(TransferRequestStatus, native_enum=False), default=TransferRequestStatus.PENDING, index=True)
    justification: Mapped[str] = mapped_column(Text)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("security_users.id", ondelete="RESTRICT"), index=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text)


class ClientMoneyReconciliation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_money_reconciliations"
    __table_args__ = (UniqueConstraint("account_id", "period_end", name="uq_client_money_recon_account_period_end"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("client_money_accounts.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    statement_ending_balance: Mapped[Decimal] = mapped_column(MONEY)
    ledger_ending_balance: Mapped[Decimal] = mapped_column(MONEY)
    difference: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[ReconciliationStatus] = mapped_column(Enum(ReconciliationStatus, native_enum=False), default=ReconciliationStatus.DRAFT, index=True)
    prepared_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("security_users.id", ondelete="RESTRICT"))
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)


class ClientMoneyReconciliationItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "client_money_reconciliation_items"

    reconciliation_id: Mapped[UUID] = mapped_column(ForeignKey("client_money_reconciliations.id", ondelete="CASCADE"), index=True)
    journal_entry_id: Mapped[UUID | None] = mapped_column(ForeignKey("client_money_journal_entries.id", ondelete="SET NULL"), nullable=True, index=True)
    statement_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    direction: Mapped[str] = mapped_column(String(12))
    reference: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[ReconciliationItemStatus] = mapped_column(Enum(ReconciliationItemStatus, native_enum=False), default=ReconciliationItemStatus.UNMATCHED, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class PaymentProviderConnection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payment_provider_connections"
    __table_args__ = (UniqueConstraint("organization_id", "provider", name="uq_payment_provider_org_kind"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    provider: Mapped[PaymentProviderKind] = mapped_column(Enum(PaymentProviderKind, native_enum=False), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="sandbox")
    public_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    secret_env_prefix: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)


class PaymentIntent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payment_intents"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    provider_connection_id: Mapped[UUID | None] = mapped_column(ForeignKey("payment_provider_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[PaymentIntentStatus] = mapped_column(Enum(PaymentIntentStatus, native_enum=False), default=PaymentIntentStatus.CREATED, index=True)
    provider_reference: Mapped[str | None] = mapped_column(String(200), index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class PaymentProviderEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payment_provider_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="uq_payment_provider_event_id"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    payment_intent_id: Mapped[UUID | None] = mapped_column(ForeignKey("payment_intents.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[PaymentProviderKind] = mapped_column(Enum(PaymentProviderKind, native_enum=False), index=True)
    provider_event_id: Mapped[str] = mapped_column(String(220), index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
