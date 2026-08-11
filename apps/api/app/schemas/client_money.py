from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.client_money import (
    ClientMoneyAccountStatus, JournalEntryStatus, JournalEntryType, PaymentIntentStatus,
    PaymentProviderKind, ReconciliationStatus, TransferRequestStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClientMoneyAccountCreate(BaseModel):
    name: str = Field(min_length=2, max_length=220)
    currency: str = "INR"
    bank_name: str | None = None
    bank_account_last4: str | None = Field(default=None, min_length=4, max_length=4)
    bank_reference: str | None = None
    require_separate_approver: bool = True
    notes: str | None = None


class ClientMoneyAccountRead(ORMModel):
    id: UUID
    name: str
    currency: str
    status: ClientMoneyAccountStatus
    bank_name: str | None
    bank_account_last4: str | None
    bank_reference: str | None
    require_separate_approver: bool
    notes: str | None
    created_at: datetime


class ClientMoneyDepositCreate(BaseModel):
    account_id: UUID
    client_id: UUID
    matter_id: UUID | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "INR"
    entry_date: date
    reference: str | None = None
    description: str = Field(default="Client money received", min_length=2, max_length=500)


class ClientMoneyJournalEntryRead(ORMModel):
    id: UUID
    account_id: UUID
    client_id: UUID
    matter_id: UUID | None
    entry_type: JournalEntryType
    status: JournalEntryStatus
    entry_date: date
    amount: Decimal
    currency: str
    reference: str | None
    description: str
    invoice_id: UUID | None
    reverses_entry_id: UUID | None
    content_hash: str
    created_at: datetime


class TransferRequestCreate(BaseModel):
    account_id: UUID
    client_id: UUID
    matter_id: UUID | None = None
    invoice_id: UUID | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "INR"
    justification: str = Field(min_length=5)


class TransferDecision(BaseModel):
    approve: bool
    note: str | None = None


class TransferRequestRead(ORMModel):
    id: UUID
    account_id: UUID
    client_id: UUID
    matter_id: UUID | None
    invoice_id: UUID | None
    amount: Decimal
    currency: str
    status: TransferRequestStatus
    justification: str
    requested_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    rejected_by_user_id: UUID | None
    rejected_at: datetime | None
    executed_by_user_id: UUID | None
    executed_at: datetime | None
    review_note: str | None
    created_at: datetime


class ReconciliationCreate(BaseModel):
    account_id: UUID
    period_start: date
    period_end: date
    statement_ending_balance: Decimal
    notes: str | None = None


class ReconciliationRead(ORMModel):
    id: UUID
    account_id: UUID
    period_start: date
    period_end: date
    statement_ending_balance: Decimal
    ledger_ending_balance: Decimal
    difference: Decimal
    status: ReconciliationStatus
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    notes: str | None
    created_at: datetime


class PaymentProviderCreate(BaseModel):
    provider: PaymentProviderKind
    enabled: bool = False
    mode: str = "sandbox"
    public_config: dict = Field(default_factory=dict)
    secret_env_prefix: str | None = None
    notes: str | None = None


class PaymentProviderRead(ORMModel):
    id: UUID
    provider: PaymentProviderKind
    enabled: bool
    mode: str
    public_config_json: dict
    secret_env_prefix: str | None
    notes: str | None


class PaymentIntentCreate(BaseModel):
    provider_connection_id: UUID | None = None
    client_id: UUID
    matter_id: UUID | None = None
    invoice_id: UUID | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "INR"
    expires_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class PaymentIntentRead(ORMModel):
    id: UUID
    provider_connection_id: UUID | None
    client_id: UUID
    matter_id: UUID | None
    invoice_id: UUID | None
    amount: Decimal
    currency: str
    status: PaymentIntentStatus
    provider_reference: str | None
    checkout_url: str | None
    expires_at: datetime | None
    metadata_json: dict
    created_at: datetime


class ClientMoneyDashboard(BaseModel):
    total_bank_balance: Decimal
    pending_transfer_total: Decimal
    unreconciled_difference: Decimal
    account_count: int
    pending_transfer_count: int
