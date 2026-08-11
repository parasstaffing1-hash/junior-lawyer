from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import ClientLedgerEntry, Invoice, InvoiceStatus, LedgerEntryType, Payment, PaymentMethod, PaymentStatus
from app.models.client_money import (
    ClientMoneyAccount, ClientMoneyAccountStatus, ClientMoneyJournalEntry, ClientMoneyJournalLine,
    ClientMoneyLedgerAccount, ClientMoneyReconciliation, JournalEntryStatus, JournalEntryType,
    PaymentIntent, PaymentProviderConnection, PaymentProviderKind, ReconciliationStatus, TransferRequestStatus,
    ClientMoneyTransferRequest,
)
from app.models.crm import Client, ClientAccessGrant, ClientSecurityProfile, MatterClientLink
from app.models.security import AccessEffect, AuditOutcome, ConfidentialityLevel, MatterAccessLevel, MatterAccessMode, OrganizationRole
from app.schemas.client_money import (
    ClientMoneyAccountCreate, ClientMoneyDepositCreate, PaymentIntentCreate, PaymentProviderCreate,
    ReconciliationCreate, TransferDecision, TransferRequestCreate,
)
from app.services.client_money.ledger import assert_balanced, content_hash, independent_approval_allowed, money, posting_lines
from app.services.client_money.providers import provider_adapter
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext
from app.services.security.permissions import decide_client_access, decide_matter_access

FINANCE_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER, OrganizationRole.BILLING}
FINANCE_VIEW_ROLES = FINANCE_ROLES | {OrganizationRole.LAWYER}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require(actor: ActorContext, roles: set[OrganizationRole]) -> None:
    if actor.role not in roles:
        raise HTTPException(403, "Your role does not permit this client-money action")


async def _audit(db: AsyncSession, actor: ActorContext, action: str, resource_type: str, resource_id: UUID | str, metadata: dict | None = None) -> None:
    await append_audit_event(db, organization_id=actor.organization_id, actor=actor, action=action,
        resource_type=resource_type, resource_id=str(resource_id), outcome=AuditOutcome.SUCCESS, metadata=metadata or {})


async def _client_allowed(db: AsyncSession, actor: ActorContext, client_id: UUID) -> Client:
    client = await db.get(Client, client_id)
    if not client or client.organization_id != actor.organization_id:
        raise HTTPException(404, "Client not found")
    if actor.role != OrganizationRole.BILLING:
        decision = await decide_client_access(db, actor, client_id, required=MatterAccessLevel.VIEW)
        if not decision.allowed:
            raise HTTPException(403, decision.reason)
    else:
        profile = await db.scalar(select(ClientSecurityProfile).where(ClientSecurityProfile.client_id == client_id))
        if profile and (profile.access_mode == MatterAccessMode.EXPLICIT or profile.classification == ConfidentialityLevel.ETHICAL_WALL):
            grant = await db.scalar(select(ClientAccessGrant).where(ClientAccessGrant.client_id == client_id,
                ClientAccessGrant.membership_id == actor.membership_id, ClientAccessGrant.effect == AccessEffect.ALLOW))
            if not grant:
                raise HTTPException(403, "Restricted client-money access requires an explicit client grant")
    return client


async def _matter_allowed(db: AsyncSession, actor: ActorContext, client_id: UUID, matter_id: UUID | None) -> None:
    if not matter_id:
        return
    link = await db.scalar(select(MatterClientLink).where(MatterClientLink.client_id == client_id, MatterClientLink.matter_id == matter_id))
    if not link:
        raise HTTPException(422, "Matter is not linked to this client")
    if actor.role != OrganizationRole.BILLING:
        decision = await decide_matter_access(db, actor, matter_id, required=MatterAccessLevel.VIEW)
        if not decision.allowed:
            raise HTTPException(403, decision.reason)


async def _account(db: AsyncSession, actor: ActorContext, account_id: UUID) -> ClientMoneyAccount:
    row = await db.get(ClientMoneyAccount, account_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Client-money account not found")
    return row


async def create_account(db: AsyncSession, actor: ActorContext, payload: ClientMoneyAccountCreate) -> ClientMoneyAccount:
    _require(actor, FINANCE_ROLES)
    row = ClientMoneyAccount(organization_id=actor.organization_id, **payload.model_dump())
    db.add(row); await db.flush(); await _audit(db, actor, "client_money.account.create", "client_money_account", row.id)
    await db.commit(); await db.refresh(row); return row


async def list_accounts(db: AsyncSession, actor: ActorContext) -> list[ClientMoneyAccount]:
    _require(actor, FINANCE_VIEW_ROLES)
    return list((await db.scalars(select(ClientMoneyAccount).where(ClientMoneyAccount.organization_id == actor.organization_id).order_by(ClientMoneyAccount.name))).all())


async def _post_entry(db: AsyncSession, actor: ActorContext, *, account: ClientMoneyAccount, client_id: UUID,
                      matter_id: UUID | None, entry_type: JournalEntryType, amount: Decimal, entry_date: date,
                      reference: str | None, description: str, invoice_id: UUID | None = None,
                      transfer_request_id: UUID | None = None) -> ClientMoneyJournalEntry:
    if account.status != ClientMoneyAccountStatus.ACTIVE:
        raise HTTPException(409, "Client-money account is not active")
    if not account.currency:
        raise HTTPException(409, "Client-money account currency is invalid")
    amount = money(amount)
    lines = posting_lines(entry_type, amount); assert_balanced(lines)
    payload = {"account_id": str(account.id), "client_id": str(client_id), "matter_id": str(matter_id) if matter_id else None,
               "type": entry_type.value, "amount": str(amount), "currency": account.currency, "date": str(entry_date),
               "reference": reference, "description": description, "invoice_id": str(invoice_id) if invoice_id else None}
    row = ClientMoneyJournalEntry(organization_id=actor.organization_id, account_id=account.id, client_id=client_id,
        matter_id=matter_id, entry_type=entry_type, entry_date=entry_date, amount=amount, currency=account.currency,
        reference=reference, description=description, transfer_request_id=transfer_request_id, invoice_id=invoice_id,
        posted_by_user_id=actor.user_id, content_hash=content_hash(payload))
    db.add(row); await db.flush()
    for line in lines:
        db.add(ClientMoneyJournalLine(journal_entry_id=row.id, ledger_account=line.account,
            client_id=client_id if line.account == ClientMoneyLedgerAccount.CLIENT_LIABILITY else None,
            matter_id=matter_id if line.account == ClientMoneyLedgerAccount.CLIENT_LIABILITY else None,
            debit=line.debit, credit=line.credit, memo=description))
    return row


async def post_deposit(db: AsyncSession, actor: ActorContext, payload: ClientMoneyDepositCreate) -> ClientMoneyJournalEntry:
    _require(actor, FINANCE_ROLES)
    account = await _account(db, actor, payload.account_id)
    await _client_allowed(db, actor, payload.client_id); await _matter_allowed(db, actor, payload.client_id, payload.matter_id)
    if payload.currency != account.currency:
        raise HTTPException(422, "Deposit currency must match the client-money account")
    row = await _post_entry(db, actor, account=account, client_id=payload.client_id, matter_id=payload.matter_id,
        entry_type=JournalEntryType.DEPOSIT, amount=payload.amount, entry_date=payload.entry_date,
        reference=payload.reference, description=payload.description)
    await _audit(db, actor, "client_money.deposit.post", "client_money_journal_entry", row.id, {"amount": str(row.amount)})
    await db.commit(); await db.refresh(row); return row


async def account_balance(db: AsyncSession, actor: ActorContext, account_id: UUID, *, through: date | None = None) -> Decimal:
    _require(actor, FINANCE_VIEW_ROLES); await _account(db, actor, account_id)
    stmt = select(func.coalesce(func.sum(ClientMoneyJournalLine.debit - ClientMoneyJournalLine.credit), 0)).join(
        ClientMoneyJournalEntry, ClientMoneyJournalEntry.id == ClientMoneyJournalLine.journal_entry_id).where(
        ClientMoneyJournalEntry.account_id == account_id, ClientMoneyJournalEntry.status == JournalEntryStatus.POSTED,
        ClientMoneyJournalLine.ledger_account == ClientMoneyLedgerAccount.BANK_CONTROL)
    if through:
        stmt = stmt.where(ClientMoneyJournalEntry.entry_date <= through)
    return money(await db.scalar(stmt) or 0)


async def client_balance(db: AsyncSession, actor: ActorContext, account_id: UUID, client_id: UUID, matter_id: UUID | None = None) -> Decimal:
    _require(actor, FINANCE_VIEW_ROLES); await _account(db, actor, account_id); await _client_allowed(db, actor, client_id)
    stmt = select(func.coalesce(func.sum(ClientMoneyJournalLine.credit - ClientMoneyJournalLine.debit), 0)).join(
        ClientMoneyJournalEntry, ClientMoneyJournalEntry.id == ClientMoneyJournalLine.journal_entry_id).where(
        ClientMoneyJournalEntry.account_id == account_id, ClientMoneyJournalEntry.status == JournalEntryStatus.POSTED,
        ClientMoneyJournalLine.ledger_account == ClientMoneyLedgerAccount.CLIENT_LIABILITY,
        ClientMoneyJournalLine.client_id == client_id)
    if matter_id:
        stmt = stmt.where(ClientMoneyJournalLine.matter_id == matter_id)
    return money(await db.scalar(stmt) or 0)


async def list_entries(db: AsyncSession, actor: ActorContext, account_id: UUID, limit: int = 200) -> list[ClientMoneyJournalEntry]:
    _require(actor, FINANCE_VIEW_ROLES); await _account(db, actor, account_id)
    rows = list((await db.scalars(select(ClientMoneyJournalEntry).where(ClientMoneyJournalEntry.account_id == account_id).order_by(ClientMoneyJournalEntry.entry_date.desc(), ClientMoneyJournalEntry.created_at.desc()).limit(limit))).all())
    visible: list[ClientMoneyJournalEntry] = []
    for row in rows:
        try:
            await _client_allowed(db, actor, row.client_id); visible.append(row)
        except HTTPException:
            continue
    return visible


async def create_transfer_request(db: AsyncSession, actor: ActorContext, payload: TransferRequestCreate) -> ClientMoneyTransferRequest:
    _require(actor, FINANCE_ROLES)
    account = await _account(db, actor, payload.account_id); await _client_allowed(db, actor, payload.client_id); await _matter_allowed(db, actor, payload.client_id, payload.matter_id)
    if payload.currency != account.currency: raise HTTPException(422, "Transfer currency must match account currency")
    if await client_balance(db, actor, account.id, payload.client_id, payload.matter_id) < money(payload.amount):
        raise HTTPException(409, "Insufficient client-money balance for this client/matter")
    if payload.invoice_id:
        invoice = await db.get(Invoice, payload.invoice_id)
        if not invoice or invoice.organization_id != actor.organization_id or invoice.client_id != payload.client_id:
            raise HTTPException(422, "Invoice is not valid for this client")
        if invoice.status not in {InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID}: raise HTTPException(409, "Invoice is not payable")
        if money(payload.amount) > money(invoice.amount_due): raise HTTPException(422, "Transfer exceeds invoice amount due")
    row = ClientMoneyTransferRequest(organization_id=actor.organization_id, requested_by_user_id=actor.user_id, **payload.model_dump())
    db.add(row); await db.flush(); await _audit(db, actor, "client_money.transfer.request", "client_money_transfer_request", row.id)
    await db.commit(); await db.refresh(row); return row


async def decide_transfer(db: AsyncSession, actor: ActorContext, request_id: UUID, payload: TransferDecision) -> ClientMoneyTransferRequest:
    _require(actor, FINANCE_ROLES)
    row = await db.get(ClientMoneyTransferRequest, request_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Transfer request not found")
    account = await _account(db, actor, row.account_id); await _client_allowed(db, actor, row.client_id)
    if row.status != TransferRequestStatus.PENDING: raise HTTPException(409, "Transfer request is not pending")
    if payload.approve:
        if not independent_approval_allowed(row.requested_by_user_id, actor.user_id, account.require_separate_approver):
            raise HTTPException(409, "This account requires a different user to approve the transfer")
        row.status = TransferRequestStatus.APPROVED; row.approved_by_user_id = actor.user_id; row.approved_at = _now()
    else:
        row.status = TransferRequestStatus.REJECTED; row.rejected_by_user_id = actor.user_id; row.rejected_at = _now()
    row.review_note = payload.note
    await _audit(db, actor, "client_money.transfer.decision", "client_money_transfer_request", row.id, {"approved": payload.approve})
    await db.commit(); await db.refresh(row); return row


async def execute_transfer(db: AsyncSession, actor: ActorContext, request_id: UUID) -> ClientMoneyTransferRequest:
    _require(actor, FINANCE_ROLES)
    row = await db.get(ClientMoneyTransferRequest, request_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Transfer request not found")
    if row.status != TransferRequestStatus.APPROVED: raise HTTPException(409, "Transfer request must be approved before execution")
    account = await _account(db, actor, row.account_id); await _client_allowed(db, actor, row.client_id); await _matter_allowed(db, actor, row.client_id, row.matter_id)
    if await client_balance(db, actor, account.id, row.client_id, row.matter_id) < money(row.amount): raise HTTPException(409, "Client-money balance changed and is now insufficient")
    invoice = await db.get(Invoice, row.invoice_id) if row.invoice_id else None
    if invoice:
        if invoice.status not in {InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID}: raise HTTPException(409, "Invoice is not payable")
        if money(row.amount) > money(invoice.amount_due): raise HTTPException(422, "Transfer exceeds invoice amount due")
    journal = await _post_entry(db, actor, account=account, client_id=row.client_id, matter_id=row.matter_id,
        entry_type=JournalEntryType.FEE_TRANSFER, amount=row.amount, entry_date=date.today(), reference=f"TR-{str(row.id)[:8]}",
        description="Approved transfer from client money to fees", invoice_id=row.invoice_id, transfer_request_id=row.id)
    if invoice:
        payment = Payment(organization_id=actor.organization_id, client_id=row.client_id, invoice_id=invoice.id, amount=row.amount,
            currency=row.currency, payment_date=date.today(), method=PaymentMethod.OTHER, status=PaymentStatus.CLEARED,
            reference=f"client-money:{row.id}", recorded_by_user_id=actor.user_id, notes="Transferred from approved client-money request")
        db.add(payment); await db.flush()
        db.add(ClientLedgerEntry(organization_id=actor.organization_id, client_id=row.client_id, invoice_id=invoice.id,
            payment_id=payment.id, entry_date=date.today(), entry_type=LedgerEntryType.PAYMENT, debit=Decimal("0"), credit=row.amount,
            currency=row.currency, description=f"Client-money transfer to invoice {invoice.invoice_number}"))
        invoice.amount_paid = money(invoice.amount_paid + row.amount); invoice.amount_due = money(invoice.grand_total - invoice.amount_paid)
        invoice.status = InvoiceStatus.PAID if invoice.amount_due <= Decimal("0.00") else InvoiceStatus.PARTIALLY_PAID
    row.status = TransferRequestStatus.EXECUTED; row.executed_by_user_id = actor.user_id; row.executed_at = _now()
    await _audit(db, actor, "client_money.transfer.execute", "client_money_transfer_request", row.id, {"journal_entry_id": str(journal.id)})
    await db.commit(); await db.refresh(row); return row


async def list_transfers(db: AsyncSession, actor: ActorContext, status: TransferRequestStatus | None = None) -> list[ClientMoneyTransferRequest]:
    _require(actor, FINANCE_VIEW_ROLES)
    stmt = select(ClientMoneyTransferRequest).where(ClientMoneyTransferRequest.organization_id == actor.organization_id)
    if status: stmt = stmt.where(ClientMoneyTransferRequest.status == status)
    rows = list((await db.scalars(stmt.order_by(ClientMoneyTransferRequest.created_at.desc()))).all())
    visible=[]
    for row in rows:
        try: await _client_allowed(db, actor, row.client_id); visible.append(row)
        except HTTPException: continue
    return visible


async def create_reconciliation(db: AsyncSession, actor: ActorContext, payload: ReconciliationCreate) -> ClientMoneyReconciliation:
    _require(actor, FINANCE_ROLES); account = await _account(db, actor, payload.account_id)
    if payload.period_end < payload.period_start: raise HTTPException(422, "period_end must not precede period_start")
    ledger = await account_balance(db, actor, account.id, through=payload.period_end)
    row = ClientMoneyReconciliation(organization_id=actor.organization_id, account_id=account.id,
        period_start=payload.period_start, period_end=payload.period_end, statement_ending_balance=money(payload.statement_ending_balance),
        ledger_ending_balance=ledger, difference=money(payload.statement_ending_balance - ledger), prepared_by_user_id=actor.user_id, notes=payload.notes)
    db.add(row); await db.flush(); await _audit(db, actor, "client_money.reconciliation.create", "client_money_reconciliation", row.id, {"difference": str(row.difference)})
    await db.commit(); await db.refresh(row); return row


async def review_reconciliation(db: AsyncSession, actor: ActorContext, reconciliation_id: UUID, *, lock: bool = False) -> ClientMoneyReconciliation:
    _require(actor, FINANCE_ROLES)
    row = await db.get(ClientMoneyReconciliation, reconciliation_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Reconciliation not found")
    if row.prepared_by_user_id == actor.user_id: raise HTTPException(409, "A different user must review the reconciliation")
    if lock and money(row.difference) != Decimal("0.00"): raise HTTPException(409, "Only a zero-difference reconciliation can be locked")
    row.reviewed_by_user_id=actor.user_id; row.reviewed_at=_now(); row.status=ReconciliationStatus.LOCKED if lock else ReconciliationStatus.REVIEWED
    await _audit(db, actor, "client_money.reconciliation.review", "client_money_reconciliation", row.id, {"locked": lock})
    await db.commit(); await db.refresh(row); return row


async def create_provider(db: AsyncSession, actor: ActorContext, payload: PaymentProviderCreate) -> PaymentProviderConnection:
    _require(actor, FINANCE_ROLES)
    row = PaymentProviderConnection(organization_id=actor.organization_id, provider=payload.provider, enabled=payload.enabled,
        mode=payload.mode, public_config_json=payload.public_config, secret_env_prefix=payload.secret_env_prefix, notes=payload.notes)
    db.add(row); await db.flush(); await _audit(db, actor, "payments.provider.create", "payment_provider_connection", row.id)
    await db.commit(); await db.refresh(row); return row


async def list_providers(db: AsyncSession, actor: ActorContext) -> list[PaymentProviderConnection]:
    _require(actor, FINANCE_VIEW_ROLES)
    return list((await db.scalars(select(PaymentProviderConnection).where(PaymentProviderConnection.organization_id == actor.organization_id))).all())


async def create_payment_intent(db: AsyncSession, actor: ActorContext, payload: PaymentIntentCreate) -> PaymentIntent:
    _require(actor, FINANCE_ROLES); await _client_allowed(db, actor, payload.client_id); await _matter_allowed(db, actor, payload.client_id, payload.matter_id)
    connection = await db.get(PaymentProviderConnection, payload.provider_connection_id) if payload.provider_connection_id else None
    provider_kind = connection.provider if connection else None
    if connection and (connection.organization_id != actor.organization_id or not connection.enabled): raise HTTPException(409, "Payment provider connection is unavailable")
    if not connection:
        connection = await db.scalar(select(PaymentProviderConnection).where(PaymentProviderConnection.organization_id == actor.organization_id,
            PaymentProviderConnection.provider == PaymentProviderKind.MANUAL))
        provider_kind = connection.provider if connection else None
    if provider_kind is None:
        raise HTTPException(409, "Configure a manual/mock payment provider first")
    if payload.invoice_id:
        invoice=await db.get(Invoice,payload.invoice_id)
        if not invoice or invoice.client_id != payload.client_id or invoice.organization_id != actor.organization_id: raise HTTPException(422,"Invoice is invalid")
        if money(payload.amount) > money(invoice.amount_due): raise HTTPException(422,"Payment intent exceeds invoice amount due")
    row = PaymentIntent(organization_id=actor.organization_id, provider_connection_id=connection.id, client_id=payload.client_id,
        matter_id=payload.matter_id, invoice_id=payload.invoice_id, amount=money(payload.amount), currency=payload.currency,
        expires_at=payload.expires_at, created_by_user_id=actor.user_id, metadata_json=payload.metadata)
    db.add(row); await db.flush()
    try:
        result = provider_adapter(provider_kind).create_intent(str(row.id))
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    row.status=result.status; row.provider_reference=result.provider_reference; row.checkout_url=result.checkout_url
    await _audit(db, actor, "payments.intent.create", "payment_intent", row.id, {"provider": provider_kind.value})
    await db.commit(); await db.refresh(row); return row


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    _require(actor, FINANCE_VIEW_ROLES)
    accounts = await list_accounts(db, actor)
    total = Decimal("0")
    for account in accounts:
        total += await account_balance(db, actor, account.id)
    total = money(total)
    pending = await list_transfers(db, actor, TransferRequestStatus.PENDING)
    pending_total = money(sum((money(row.amount) for row in pending), Decimal("0")))
    recs = list((await db.scalars(select(ClientMoneyReconciliation).where(ClientMoneyReconciliation.organization_id == actor.organization_id,
        ClientMoneyReconciliation.status != ReconciliationStatus.LOCKED))).all())
    diff = money(sum((abs(money(r.difference)) for r in recs), Decimal("0")))
    return {"total_bank_balance": total, "pending_transfer_total": pending_total, "unreconciled_difference": diff,
            "account_count": len(accounts), "pending_transfer_count": len(pending)}
