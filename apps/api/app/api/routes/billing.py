from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.billing import ExpenseStatus
from app.schemas.billing import (
    BillingOverview, BillingProfileRead, BillingProfileUpdate, ClientStatement, ExpenseCreate,
    ExpenseRead, FeeArrangementCreate, FeeArrangementRead, InvoiceCreate, InvoiceIssueRequest,
    InvoiceRead, InvoiceReviewRequest, PaymentCreate, PaymentRead, RateCardCreate, RateCreate,
)
from app.services.billing import service
from app.services.portal import service as portal_service
from app.schemas.portal import PortalMessageCreate, PortalMessageRead, PortalRequestCreate, PortalRequestRead, PortalShareCreate, PortalShareRead
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor


router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/overview", response_model=BillingOverview)
async def overview(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return BillingOverview(**await service.overview(db, actor))


@router.get("/profile", response_model=BillingProfileRead)
async def profile(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return BillingProfileRead.model_validate(await service.get_or_create_profile(db, actor))


@router.put("/profile", response_model=BillingProfileRead)
async def put_profile(payload: BillingProfileUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return BillingProfileRead.model_validate(await service.update_profile(db, actor, payload))


@router.get("/rate-cards")
async def rate_cards(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    rows = await service.list_rate_cards(db, actor)
    return [{"id": str(r.id), "name": r.name, "currency": r.currency, "is_default": r.is_default, "is_active": r.is_active, "notes": r.notes} for r in rows]


@router.post("/rate-cards", status_code=201)
async def create_rate_card(payload: RateCardCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    r = await service.create_rate_card(db, actor, payload)
    return {"id": str(r.id), "name": r.name, "currency": r.currency, "is_default": r.is_default, "is_active": r.is_active}


@router.post("/rate-cards/{rate_card_id}/rates", status_code=201)
async def create_rate(rate_card_id: UUID, payload: RateCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    r = await service.add_rate(db, actor, rate_card_id, payload)
    return {"id": str(r.id), "rate_card_id": str(r.rate_card_id), "membership_id": str(r.membership_id) if r.membership_id else None, "role_label": r.role_label, "hourly_rate": str(r.hourly_rate)}


@router.get("/fee-arrangements", response_model=list[FeeArrangementRead])
async def fee_arrangements(client_id: UUID | None = None, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [FeeArrangementRead.model_validate(r) for r in await service.list_fee_arrangements(db, actor, client_id)]


@router.post("/fee-arrangements", response_model=FeeArrangementRead, status_code=201)
async def create_fee_arrangement(payload: FeeArrangementCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return FeeArrangementRead.model_validate(await service.create_fee_arrangement(db, actor, payload))


@router.get("/expenses", response_model=list[ExpenseRead])
async def expenses(limit: int = Query(200, ge=1, le=1000), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ExpenseRead.model_validate(r) for r in await service.list_expenses(db, actor, limit)]


@router.post("/expenses", response_model=ExpenseRead, status_code=201)
async def create_expense(payload: ExpenseCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ExpenseRead.model_validate(await service.create_expense(db, actor, payload))


@router.patch("/expenses/{expense_id}/status", response_model=ExpenseRead)
async def expense_status(expense_id: UUID, status: ExpenseStatus, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ExpenseRead.model_validate(await service.update_expense_status(db, actor, expense_id, status))


@router.get("/invoices", response_model=list[InvoiceRead])
async def invoices(client_id: UUID | None = None, limit: int = Query(200, ge=1, le=1000), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [InvoiceRead.model_validate(r) for r in await service.list_invoices(db, actor, client_id, limit)]


@router.post("/invoices", response_model=InvoiceRead, status_code=201)
async def create_invoice(payload: InvoiceCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return InvoiceRead.model_validate(await service.create_invoice(db, actor, payload))


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
async def invoice(invoice_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return InvoiceRead.model_validate(await service.get_invoice(db, actor, invoice_id))


@router.post("/invoices/{invoice_id}/review", response_model=InvoiceRead)
async def review_invoice(invoice_id: UUID, payload: InvoiceReviewRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return InvoiceRead.model_validate(await service.review_invoice(db, actor, invoice_id, payload))


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceRead)
async def issue_invoice(invoice_id: UUID, payload: InvoiceIssueRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return InvoiceRead.model_validate(await service.issue_invoice(db, actor, invoice_id, payload))


@router.get("/payments", response_model=list[PaymentRead])
async def payments(client_id: UUID | None = None, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [PaymentRead.model_validate(r) for r in await service.list_payments(db, actor, client_id)]


@router.post("/payments", response_model=PaymentRead, status_code=201)
async def create_payment(payload: PaymentCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return PaymentRead.model_validate(await service.record_payment(db, actor, payload))


@router.get("/clients/{client_id}/statement", response_model=ClientStatement)
async def statement(client_id: UUID, currency: str = "INR", actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientStatement(**await service.client_statement(db, actor, client_id, currency))


@router.post("/portal/access/{access_id}/activation-token")
async def portal_activation_token(access_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await portal_service.issue_activation_token(db, actor, access_id)


@router.get("/portal/access/{access_id}/shares", response_model=list[PortalShareRead])
async def portal_shares(access_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [PortalShareRead.model_validate(r) for r in await portal_service.list_internal_shares(db, actor, access_id)]


@router.post("/portal/shares", response_model=PortalShareRead, status_code=201)
async def create_portal_share(payload: PortalShareCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return PortalShareRead.model_validate(await portal_service.create_share(db, actor, payload))


@router.post("/portal/requests", response_model=PortalRequestRead, status_code=201)
async def create_portal_request(payload: PortalRequestCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return PortalRequestRead.model_validate(await portal_service.create_request(db, actor, payload))


@router.post("/portal/access/{access_id}/messages", response_model=PortalMessageRead, status_code=201)
async def portal_firm_message(access_id: UUID, payload: PortalMessageCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return PortalMessageRead.model_validate(await portal_service.firm_message(db, actor, access_id, payload.matter_id, payload.body))
