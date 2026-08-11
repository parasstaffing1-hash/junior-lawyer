from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing import (
    BillingRate, BillingRateCard, ClientLedgerEntry, Expense, ExpenseStatus, FeeArrangement,
    Invoice, InvoiceLine, InvoiceLineKind, InvoiceStatus, InvoiceVersion, LedgerEntryType,
    OrganizationBillingProfile, Payment, PaymentStatus,
)
from app.models.crm import Client, ClientAccessGrant, ClientSecurityProfile, MatterClientLink, TimeEntry, TimeEntryStatus
from app.models.security import AccessEffect, AuditOutcome, ConfidentialityLevel, MatterAccessLevel, MatterAccessMode, OrganizationRole
from app.schemas.billing import (
    BillingProfileUpdate, ExpenseCreate, FeeArrangementCreate, InvoiceCreate, InvoiceLineCreate,
    InvoiceReviewRequest, InvoiceIssueRequest, PaymentCreate, RateCardCreate, RateCreate,
)
from app.services.billing.calculator import aggregate_lines, calculate_line, money, stable_hash
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext
from app.services.security.permissions import decide_client_access, decide_matter_access, visible_client_ids


BILLING_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER, OrganizationRole.LAWYER, OrganizationRole.BILLING}
BILLING_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER, OrganizationRole.BILLING}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_role(actor: ActorContext, allowed: set[OrganizationRole]) -> None:
    if actor.role not in allowed:
        raise HTTPException(403, "Your role does not permit this billing action")


async def _audit(db: AsyncSession, actor: ActorContext, action: str, resource_type: str, resource_id: UUID | str, metadata: dict | None = None) -> None:
    await append_audit_event(
        db, organization_id=actor.organization_id, actor=actor, action=action,
        resource_type=resource_type, resource_id=str(resource_id), outcome=AuditOutcome.SUCCESS,
        metadata=metadata or {},
    )


async def _billing_client_allowed(db: AsyncSession, actor: ActorContext, client_id: UUID) -> Client:
    client = await db.get(Client, client_id)
    if not client or client.organization_id != actor.organization_id:
        raise HTTPException(404, "Client not found")
    if actor.role != OrganizationRole.BILLING:
        decision = await decide_client_access(db, actor, client_id, required=MatterAccessLevel.VIEW)
        if not decision.allowed:
            raise HTTPException(403, decision.reason)
        return client

    profile = await db.scalar(select(ClientSecurityProfile).where(ClientSecurityProfile.client_id == client_id))
    if profile and (profile.access_mode == MatterAccessMode.EXPLICIT or profile.classification == ConfidentialityLevel.ETHICAL_WALL):
        grant = await db.scalar(select(ClientAccessGrant).where(
            ClientAccessGrant.client_id == client_id,
            ClientAccessGrant.membership_id == actor.membership_id,
            ClientAccessGrant.effect == AccessEffect.ALLOW,
        ))
        if not grant:
            raise HTTPException(403, "Restricted client billing access requires an explicit grant")
    return client


async def _visible_billing_client_ids(db: AsyncSession, actor: ActorContext) -> set[UUID]:
    if actor.role != OrganizationRole.BILLING:
        return await visible_client_ids(db, actor)
    ids = list((await db.scalars(select(Client.id).where(Client.organization_id == actor.organization_id))).all())
    visible: set[UUID] = set()
    for client_id in ids:
        try:
            await _billing_client_allowed(db, actor, client_id)
            visible.add(client_id)
        except HTTPException:
            pass
    return visible


async def get_or_create_profile(db: AsyncSession, actor: ActorContext) -> OrganizationBillingProfile:
    _require_role(actor, BILLING_ROLES)
    profile = await db.scalar(select(OrganizationBillingProfile).where(OrganizationBillingProfile.organization_id == actor.organization_id))
    if not profile:
        profile = OrganizationBillingProfile(organization_id=actor.organization_id)
        db.add(profile)
        await db.commit(); await db.refresh(profile)
    return profile


async def update_profile(db: AsyncSession, actor: ActorContext, payload: BillingProfileUpdate) -> OrganizationBillingProfile:
    _require_role(actor, BILLING_ADMIN_ROLES)
    profile = await get_or_create_profile(db, actor)
    data = payload.model_dump()
    data["bank_details_json"] = data.pop("bank_details")
    data["tax_configuration_json"] = data.pop("tax_configuration")
    for key, value in data.items(): setattr(profile, key, value)
    await _audit(db, actor, "billing.profile.update", "organization_billing_profile", profile.id)
    await db.commit(); await db.refresh(profile)
    return profile


async def create_rate_card(db: AsyncSession, actor: ActorContext, payload: RateCardCreate) -> BillingRateCard:
    _require_role(actor, BILLING_ADMIN_ROLES)
    if payload.is_default:
        for row in (await db.scalars(select(BillingRateCard).where(BillingRateCard.organization_id == actor.organization_id, BillingRateCard.is_default.is_(True)))).all():
            row.is_default = False
    row = BillingRateCard(organization_id=actor.organization_id, **payload.model_dump())
    db.add(row); await db.flush(); await _audit(db, actor, "billing.rate_card.create", "billing_rate_card", row.id)
    await db.commit(); await db.refresh(row); return row


async def add_rate(db: AsyncSession, actor: ActorContext, rate_card_id: UUID, payload: RateCreate) -> BillingRate:
    _require_role(actor, BILLING_ADMIN_ROLES)
    card = await db.get(BillingRateCard, rate_card_id)
    if not card or card.organization_id != actor.organization_id: raise HTTPException(404, "Rate card not found")
    row = BillingRate(rate_card_id=card.id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def list_rate_cards(db: AsyncSession, actor: ActorContext) -> list[BillingRateCard]:
    _require_role(actor, BILLING_ROLES)
    return list((await db.scalars(select(BillingRateCard).where(BillingRateCard.organization_id == actor.organization_id).order_by(BillingRateCard.is_default.desc(), BillingRateCard.name))).all())


async def create_fee_arrangement(db: AsyncSession, actor: ActorContext, payload: FeeArrangementCreate) -> FeeArrangement:
    _require_role(actor, BILLING_ADMIN_ROLES)
    await _billing_client_allowed(db, actor, payload.client_id)
    if payload.matter_id and actor.role != OrganizationRole.BILLING:
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.VIEW)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    data = payload.model_dump()
    data["tax_treatment_json"] = data.pop("tax_treatment")
    row = FeeArrangement(organization_id=actor.organization_id, **data)
    db.add(row); await db.flush(); await _audit(db, actor, "billing.fee_arrangement.create", "fee_arrangement", row.id)
    await db.commit(); await db.refresh(row); return row


async def list_fee_arrangements(db: AsyncSession, actor: ActorContext, client_id: UUID | None = None) -> list[FeeArrangement]:
    _require_role(actor, BILLING_ROLES)
    visible = await _visible_billing_client_ids(db, actor)
    if client_id:
        await _billing_client_allowed(db, actor, client_id); visible &= {client_id}
    if not visible: return []
    return list((await db.scalars(select(FeeArrangement).where(FeeArrangement.organization_id == actor.organization_id, FeeArrangement.client_id.in_(visible)).order_by(FeeArrangement.created_at.desc()))).all())


async def create_expense(db: AsyncSession, actor: ActorContext, payload: ExpenseCreate) -> Expense:
    _require_role(actor, BILLING_ROLES)
    if payload.client_id: await _billing_client_allowed(db, actor, payload.client_id)
    if payload.matter_id and actor.role != OrganizationRole.BILLING:
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    row = Expense(organization_id=actor.organization_id, incurred_by_user_id=actor.user_id, **payload.model_dump())
    db.add(row); await db.flush(); await _audit(db, actor, "billing.expense.create", "expense", row.id)
    await db.commit(); await db.refresh(row); return row


async def list_expenses(db: AsyncSession, actor: ActorContext, limit: int = 200) -> list[Expense]:
    _require_role(actor, BILLING_ROLES)
    visible = await _visible_billing_client_ids(db, actor)
    stmt = select(Expense).where(Expense.organization_id == actor.organization_id).order_by(Expense.expense_date.desc()).limit(limit)
    rows = list((await db.scalars(stmt)).all())
    return [r for r in rows if r.client_id is None or r.client_id in visible]


async def _next_invoice_number(db: AsyncSession, actor: ActorContext, issue_date: date | None) -> tuple[OrganizationBillingProfile, str]:
    profile = await get_or_create_profile(db, actor)
    year = (issue_date or date.today()).year
    seq = profile.next_invoice_sequence
    number = f"{profile.invoice_prefix}/{year}/{seq:05d}"
    profile.next_invoice_sequence = seq + 1
    return profile, number


async def _validate_line_source(db: AsyncSession, actor: ActorContext, client_id: UUID, line: InvoiceLineCreate) -> None:
    if line.source_time_entry_id:
        entry = await db.get(TimeEntry, line.source_time_entry_id)
        if not entry or entry.organization_id != actor.organization_id: raise HTTPException(422, "Time entry not found")
        if entry.client_id and entry.client_id != client_id: raise HTTPException(422, "Time entry belongs to another client")
        if entry.status == TimeEntryStatus.INVOICED: raise HTTPException(409, "Time entry is already invoiced")
    if line.source_expense_id:
        expense = await db.get(Expense, line.source_expense_id)
        if not expense or expense.organization_id != actor.organization_id: raise HTTPException(422, "Expense not found")
        if expense.client_id and expense.client_id != client_id: raise HTTPException(422, "Expense belongs to another client")
        if expense.status == ExpenseStatus.BILLED: raise HTTPException(409, "Expense is already billed")


def _apply_line_math(row: InvoiceLine) -> None:
    totals = calculate_line(
        quantity=row.quantity, unit_price=row.unit_price, discount_amount=row.discount_amount,
        cgst_rate=row.cgst_rate, sgst_rate=row.sgst_rate, igst_rate=row.igst_rate, cess_rate=row.cess_rate,
    )
    row.taxable_amount = totals.taxable
    row.cgst_amount = totals.cgst; row.sgst_amount = totals.sgst; row.igst_amount = totals.igst; row.cess_amount = totals.cess
    row.line_total = totals.total


def _apply_invoice_totals(invoice: Invoice) -> None:
    totals = aggregate_lines([
        calculate_line(
            quantity=line.quantity, unit_price=line.unit_price, discount_amount=line.discount_amount,
            cgst_rate=line.cgst_rate, sgst_rate=line.sgst_rate, igst_rate=line.igst_rate, cess_rate=line.cess_rate,
        ) for line in invoice.lines
    ])
    invoice.subtotal = totals.subtotal; invoice.discount_total = totals.discount_total; invoice.taxable_total = totals.taxable_total
    invoice.cgst_total = totals.cgst_total; invoice.sgst_total = totals.sgst_total; invoice.igst_total = totals.igst_total; invoice.cess_total = totals.cess_total
    invoice.tax_total = totals.tax_total; invoice.grand_total = totals.grand_total
    invoice.amount_due = money(invoice.grand_total - invoice.amount_paid)


def invoice_snapshot(invoice: Invoice) -> dict:
    return {
        "invoice_number": invoice.invoice_number, "client_id": str(invoice.client_id), "matter_id": str(invoice.matter_id) if invoice.matter_id else None,
        "issue_date": str(invoice.issue_date) if invoice.issue_date else None, "due_date": str(invoice.due_date) if invoice.due_date else None,
        "currency": invoice.currency, "supplier": {"name": invoice.supplier_name, "address": invoice.supplier_address, "gstin": invoice.supplier_gstin, "state_code": invoice.supplier_state_code},
        "client": {"name": invoice.client_name, "address": invoice.client_address, "gstin": invoice.client_gstin, "state_code": invoice.client_state_code},
        "place_of_supply": invoice.place_of_supply, "reverse_charge": invoice.reverse_charge,
        "totals": {"subtotal": str(invoice.subtotal), "discount": str(invoice.discount_total), "taxable": str(invoice.taxable_total), "cgst": str(invoice.cgst_total), "sgst": str(invoice.sgst_total), "igst": str(invoice.igst_total), "cess": str(invoice.cess_total), "tax": str(invoice.tax_total), "grand": str(invoice.grand_total)},
        "lines": [{
            "kind": line.kind.value, "description": line.description, "service_code": line.service_code,
            "quantity": str(line.quantity), "unit_price": str(line.unit_price), "discount": str(line.discount_amount),
            "taxable": str(line.taxable_amount), "rates": {"cgst": str(line.cgst_rate), "sgst": str(line.sgst_rate), "igst": str(line.igst_rate), "cess": str(line.cess_rate)},
            "tax": {"cgst": str(line.cgst_amount), "sgst": str(line.sgst_amount), "igst": str(line.igst_amount), "cess": str(line.cess_amount)}, "line_total": str(line.line_total),
        } for line in invoice.lines],
        "notes": invoice.notes,
    }


def tax_review_findings(invoice: Invoice) -> list[dict]:
    findings: list[dict] = []
    if not invoice.lines: findings.append({"level": "high", "code": "no_lines", "message": "Invoice has no billable lines."})
    if invoice.tax_total > 0 and not invoice.supplier_gstin:
        findings.append({"level": "high", "code": "supplier_gstin_missing", "message": "Tax is applied but supplier GSTIN is not recorded. Verify invoice particulars before issue."})
    if invoice.tax_total > 0 and not invoice.place_of_supply:
        findings.append({"level": "medium", "code": "place_of_supply_missing", "message": "Tax is applied but place of supply is blank. Verify tax treatment."})
    if any((line.cgst_rate > 0 or line.sgst_rate > 0 or line.igst_rate > 0) and not line.service_code for line in invoice.lines):
        findings.append({"level": "medium", "code": "service_code_missing", "message": "At least one taxed line has no service/classification code."})
    return findings


async def create_invoice(db: AsyncSession, actor: ActorContext, payload: InvoiceCreate) -> Invoice:
    _require_role(actor, BILLING_ROLES)
    client = await _billing_client_allowed(db, actor, payload.client_id)
    if payload.matter_id:
        link = await db.scalar(select(MatterClientLink).where(MatterClientLink.matter_id == payload.matter_id, MatterClientLink.client_id == client.id))
        if not link: raise HTTPException(422, "Selected matter is not linked to this client")
        if actor.role != OrganizationRole.BILLING:
            decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.VIEW)
            if not decision.allowed: raise HTTPException(403, decision.reason)
    for line in payload.lines: await _validate_line_source(db, actor, client.id, line)
    profile, invoice_number = await _next_invoice_number(db, actor, payload.issue_date)
    issue = payload.issue_date
    due = payload.due_date or (issue + timedelta(days=profile.default_payment_terms_days) if issue else None)
    row = Invoice(
        organization_id=actor.organization_id, client_id=client.id, matter_id=payload.matter_id,
        fee_arrangement_id=payload.fee_arrangement_id, invoice_number=invoice_number, issue_date=issue,
        due_date=due, currency=payload.currency, supplier_name=profile.legal_name, supplier_address=profile.billing_address,
        supplier_gstin=profile.gstin, supplier_state_code=profile.state_code, supplier_email=profile.email,
        client_name=client.legal_name or client.display_name, client_address=payload.client_address or client.billing_address,
        client_gstin=payload.client_gstin, client_state_code=payload.client_state_code, place_of_supply=payload.place_of_supply,
        reverse_charge=payload.reverse_charge, notes=payload.notes, metadata_json=payload.metadata,
    )
    db.add(row); await db.flush()
    for order, item in enumerate(payload.lines):
        data = item.model_dump(); data["metadata_json"] = data.pop("metadata")
        line = InvoiceLine(invoice_id=row.id, sort_order=order, **data); _apply_line_math(line); db.add(line)
    await db.flush(); await db.refresh(row, attribute_names=["lines"]); _apply_invoice_totals(row)
    row.metadata_json = {**row.metadata_json, "tax_review_findings": tax_review_findings(row)}
    await _audit(db, actor, "billing.invoice.create", "invoice", row.id, {"invoice_number": row.invoice_number})
    await db.commit(); return await get_invoice(db, actor, row.id)


async def list_invoices(db: AsyncSession, actor: ActorContext, client_id: UUID | None = None, limit: int = 200) -> list[Invoice]:
    _require_role(actor, BILLING_ROLES)
    visible = await _visible_billing_client_ids(db, actor)
    if client_id:
        await _billing_client_allowed(db, actor, client_id); visible &= {client_id}
    if not visible: return []
    stmt = select(Invoice).options(selectinload(Invoice.lines)).where(Invoice.organization_id == actor.organization_id, Invoice.client_id.in_(visible)).order_by(Invoice.created_at.desc()).limit(limit)
    return list((await db.scalars(stmt)).all())


async def get_invoice(db: AsyncSession, actor: ActorContext, invoice_id: UUID) -> Invoice:
    _require_role(actor, BILLING_ROLES)
    invoice = await db.scalar(select(Invoice).options(selectinload(Invoice.lines)).where(Invoice.id == invoice_id))
    if not invoice or invoice.organization_id != actor.organization_id: raise HTTPException(404, "Invoice not found")
    await _billing_client_allowed(db, actor, invoice.client_id)
    return invoice


async def review_invoice(db: AsyncSession, actor: ActorContext, invoice_id: UUID, payload: InvoiceReviewRequest) -> Invoice:
    _require_role(actor, BILLING_ADMIN_ROLES)
    invoice = await get_invoice(db, actor, invoice_id)
    if invoice.status in {InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID, InvoiceStatus.VOID}:
        raise HTTPException(409, "Issued/paid/void invoices cannot be re-reviewed as drafts")
    _apply_invoice_totals(invoice)
    findings = tax_review_findings(invoice)
    invoice.metadata_json = {**invoice.metadata_json, "tax_review_findings": findings, "review_note": payload.note}
    invoice.tax_treatment_reviewed = payload.tax_treatment_reviewed
    invoice.reviewed_by_user_id = actor.user_id if payload.tax_treatment_reviewed else None
    invoice.reviewed_at = _now() if payload.tax_treatment_reviewed else None
    invoice.status = InvoiceStatus.REVIEW if payload.tax_treatment_reviewed else InvoiceStatus.DRAFT
    await _audit(db, actor, "billing.invoice.review", "invoice", invoice.id, {"findings": len(findings), "tax_treatment_reviewed": payload.tax_treatment_reviewed})
    await db.commit(); return await get_invoice(db, actor, invoice.id)


async def issue_invoice(db: AsyncSession, actor: ActorContext, invoice_id: UUID, payload: InvoiceIssueRequest) -> Invoice:
    _require_role(actor, BILLING_ADMIN_ROLES)
    invoice = await get_invoice(db, actor, invoice_id)
    if invoice.status not in {InvoiceStatus.DRAFT, InvoiceStatus.REVIEW}: raise HTTPException(409, "Invoice is not issuable from its current state")
    if not invoice.tax_treatment_reviewed: raise HTTPException(409, "Tax treatment must be reviewed before issue")
    if not invoice.lines: raise HTTPException(409, "Invoice has no lines")
    if invoice.issue_date is None: invoice.issue_date = date.today()
    profile = await get_or_create_profile(db, actor)
    if invoice.due_date is None: invoice.due_date = invoice.issue_date + timedelta(days=profile.default_payment_terms_days)
    _apply_invoice_totals(invoice)
    snapshot = invoice_snapshot(invoice); digest = stable_hash(snapshot)
    version_count = await db.scalar(select(func.count(InvoiceVersion.id)).where(InvoiceVersion.invoice_id == invoice.id)) or 0
    db.add(InvoiceVersion(invoice_id=invoice.id, version_number=version_count + 1, snapshot_json=snapshot, content_hash=digest, created_by_user_id=actor.user_id))
    invoice.content_hash = digest; invoice.status = InvoiceStatus.ISSUED; invoice.issued_by_user_id = actor.user_id; invoice.issued_at = _now()
    invoice.irn = payload.irn; invoice.acknowledgement_number = payload.acknowledgement_number; invoice.acknowledgement_date = payload.acknowledgement_date
    db.add(ClientLedgerEntry(organization_id=actor.organization_id, client_id=invoice.client_id, invoice_id=invoice.id, entry_date=invoice.issue_date, entry_type=LedgerEntryType.INVOICE, debit=invoice.grand_total, credit=Decimal("0"), currency=invoice.currency, description=f"Invoice {invoice.invoice_number}"))
    for line in invoice.lines:
        if line.source_time_entry_id:
            entry = await db.get(TimeEntry, line.source_time_entry_id)
            if entry: entry.status = TimeEntryStatus.INVOICED
        if line.source_expense_id:
            expense = await db.get(Expense, line.source_expense_id)
            if expense: expense.status = ExpenseStatus.BILLED
    await _audit(db, actor, "billing.invoice.issue", "invoice", invoice.id, {"invoice_number": invoice.invoice_number, "hash": digest})
    await db.commit(); return await get_invoice(db, actor, invoice.id)


async def record_payment(db: AsyncSession, actor: ActorContext, payload: PaymentCreate) -> Payment:
    _require_role(actor, BILLING_ADMIN_ROLES)
    client = await _billing_client_allowed(db, actor, payload.client_id)
    invoice = None
    if payload.invoice_id:
        invoice = await get_invoice(db, actor, payload.invoice_id)
        if invoice.client_id != client.id: raise HTTPException(422, "Invoice belongs to another client")
        if invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.REVIEW, InvoiceStatus.VOID}: raise HTTPException(409, "Payment cannot be allocated to this invoice state")
        if payload.currency != invoice.currency: raise HTTPException(422, "Payment currency must match invoice currency")
        if payload.status == PaymentStatus.CLEARED and money(payload.amount) > money(invoice.amount_due):
            raise HTTPException(422, "Payment exceeds the invoice amount due")
    row = Payment(organization_id=actor.organization_id, recorded_by_user_id=actor.user_id, **payload.model_dump())
    db.add(row); await db.flush()
    if row.status == PaymentStatus.CLEARED:
        db.add(ClientLedgerEntry(organization_id=actor.organization_id, client_id=client.id, invoice_id=invoice.id if invoice else None, payment_id=row.id, entry_date=row.payment_date, entry_type=LedgerEntryType.PAYMENT, debit=Decimal("0"), credit=row.amount, currency=row.currency, description=f"Payment {row.reference or row.id}"))
        if invoice:
            invoice.amount_paid = money(invoice.amount_paid + row.amount); invoice.amount_due = money(invoice.grand_total - invoice.amount_paid)
            invoice.status = InvoiceStatus.PAID if invoice.amount_due <= Decimal("0.00") else InvoiceStatus.PARTIALLY_PAID
    await _audit(db, actor, "billing.payment.record", "payment", row.id, {"invoice_id": str(payload.invoice_id) if payload.invoice_id else None})
    await db.commit(); await db.refresh(row); return row


async def client_statement(db: AsyncSession, actor: ActorContext, client_id: UUID, currency: str = "INR") -> dict:
    _require_role(actor, BILLING_ROLES); await _billing_client_allowed(db, actor, client_id)
    rows = list((await db.scalars(select(ClientLedgerEntry).where(ClientLedgerEntry.organization_id == actor.organization_id, ClientLedgerEntry.client_id == client_id, ClientLedgerEntry.currency == currency).order_by(ClientLedgerEntry.entry_date, ClientLedgerEntry.created_at))).all())
    balance = Decimal("0.00"); out=[]
    for row in rows:
        balance = money(balance + row.debit - row.credit)
        out.append({"id": row.id, "entry_date": row.entry_date, "entry_type": row.entry_type.value, "description": row.description, "debit": row.debit, "credit": row.credit, "balance": balance, "currency": row.currency, "invoice_id": row.invoice_id, "payment_id": row.payment_id})
    return {"client_id": client_id, "currency": currency, "opening_balance": Decimal("0.00"), "closing_balance": balance, "rows": out}


async def overview(db: AsyncSession, actor: ActorContext) -> dict:
    _require_role(actor, BILLING_ROLES)
    invoices = await list_invoices(db, actor, limit=1000)
    today = date.today()
    draft = sum(1 for i in invoices if i.status in {InvoiceStatus.DRAFT, InvoiceStatus.REVIEW})
    issued = sum(1 for i in invoices if i.status in {InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID})
    overdue = sum(1 for i in invoices if i.status in {InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID} and i.due_date and i.due_date < today and i.amount_due > 0)
    outstanding = money(sum((i.amount_due for i in invoices if i.status not in {InvoiceStatus.VOID, InvoiceStatus.DRAFT, InvoiceStatus.REVIEW}), Decimal("0")))
    visible = await _visible_billing_client_ids(db, actor)
    time_stmt = select(func.coalesce(func.sum(TimeEntry.minutes), 0)).where(TimeEntry.organization_id == actor.organization_id, TimeEntry.status != TimeEntryStatus.INVOICED)
    if visible: time_stmt = time_stmt.where((TimeEntry.client_id.is_(None)) | (TimeEntry.client_id.in_(visible)))
    else: time_stmt = time_stmt.where(TimeEntry.client_id.is_(None))
    unbilled = int(await db.scalar(time_stmt) or 0)
    exp_stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.organization_id == actor.organization_id, Expense.status == ExpenseStatus.APPROVED)
    if visible: exp_stmt = exp_stmt.where((Expense.client_id.is_(None)) | (Expense.client_id.in_(visible)))
    else: exp_stmt = exp_stmt.where(Expense.client_id.is_(None))
    approved_expenses = money(await db.scalar(exp_stmt) or 0)
    return {"draft_invoices": draft, "issued_invoices": issued, "overdue_invoices": overdue, "outstanding_amount": outstanding, "unbilled_minutes": unbilled, "approved_expenses": approved_expenses}

async def update_expense_status(db: AsyncSession, actor: ActorContext, expense_id: UUID, new_status: ExpenseStatus) -> Expense:
    _require_role(actor, BILLING_ADMIN_ROLES)
    row = await db.get(Expense, expense_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Expense not found")
    if row.client_id: await _billing_client_allowed(db, actor, row.client_id)
    if row.status == ExpenseStatus.BILLED and new_status != ExpenseStatus.BILLED:
        raise HTTPException(409, "Billed expenses cannot be moved back without credit/rebilling workflow")
    row.status = new_status
    await _audit(db, actor, "billing.expense.status", "expense", row.id, {"status": new_status.value})
    await db.commit(); await db.refresh(row); return row


async def list_payments(db: AsyncSession, actor: ActorContext, client_id: UUID | None = None, limit: int = 200) -> list[Payment]:
    _require_role(actor, BILLING_ROLES)
    visible = await _visible_billing_client_ids(db, actor)
    if client_id:
        await _billing_client_allowed(db, actor, client_id); visible &= {client_id}
    if not visible: return []
    return list((await db.scalars(select(Payment).where(Payment.organization_id == actor.organization_id, Payment.client_id.in_(visible)).order_by(Payment.payment_date.desc(), Payment.created_at.desc()).limit(limit))).all())
