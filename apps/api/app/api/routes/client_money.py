from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.client_money import TransferRequestStatus
from app.schemas.client_money import (
    ClientMoneyAccountCreate, ClientMoneyAccountRead, ClientMoneyDashboard, ClientMoneyDepositCreate,
    ClientMoneyJournalEntryRead, PaymentIntentCreate, PaymentIntentRead, PaymentProviderCreate,
    PaymentProviderRead, ReconciliationCreate, ReconciliationRead, TransferDecision,
    TransferRequestCreate, TransferRequestRead,
)
from app.services.client_money import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/client-money", tags=["client-money"])


@router.get("/dashboard", response_model=ClientMoneyDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientMoneyDashboard(**await service.dashboard(db, actor))


@router.get("/accounts", response_model=list[ClientMoneyAccountRead])
async def accounts(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ClientMoneyAccountRead.model_validate(r) for r in await service.list_accounts(db, actor)]


@router.post("/accounts", response_model=ClientMoneyAccountRead, status_code=201)
async def create_account(payload: ClientMoneyAccountCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientMoneyAccountRead.model_validate(await service.create_account(db, actor, payload))


@router.get("/accounts/{account_id}/balance")
async def balance(account_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return {"account_id": str(account_id), "balance": str(await service.account_balance(db, actor, account_id))}


@router.get("/accounts/{account_id}/clients/{client_id}/balance")
async def client_balance(account_id: UUID, client_id: UUID, matter_id: UUID | None = None, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return {"account_id": str(account_id), "client_id": str(client_id), "matter_id": str(matter_id) if matter_id else None,
            "balance": str(await service.client_balance(db, actor, account_id, client_id, matter_id))}


@router.get("/accounts/{account_id}/entries", response_model=list[ClientMoneyJournalEntryRead])
async def entries(account_id: UUID, limit: int = Query(200, ge=1, le=1000), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ClientMoneyJournalEntryRead.model_validate(r) for r in await service.list_entries(db, actor, account_id, limit)]


@router.post("/deposits", response_model=ClientMoneyJournalEntryRead, status_code=201)
async def deposit(payload: ClientMoneyDepositCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ClientMoneyJournalEntryRead.model_validate(await service.post_deposit(db, actor, payload))


@router.get("/transfers", response_model=list[TransferRequestRead])
async def transfers(status: TransferRequestStatus | None = None, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [TransferRequestRead.model_validate(r) for r in await service.list_transfers(db, actor, status)]


@router.post("/transfers", response_model=TransferRequestRead, status_code=201)
async def transfer_request(payload: TransferRequestCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return TransferRequestRead.model_validate(await service.create_transfer_request(db, actor, payload))


@router.post("/transfers/{request_id}/decision", response_model=TransferRequestRead)
async def transfer_decision(request_id: UUID, payload: TransferDecision, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return TransferRequestRead.model_validate(await service.decide_transfer(db, actor, request_id, payload))


@router.post("/transfers/{request_id}/execute", response_model=TransferRequestRead)
async def transfer_execute(request_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return TransferRequestRead.model_validate(await service.execute_transfer(db, actor, request_id))


@router.post("/reconciliations", response_model=ReconciliationRead, status_code=201)
async def reconciliation(payload: ReconciliationCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ReconciliationRead.model_validate(await service.create_reconciliation(db, actor, payload))


@router.post("/reconciliations/{reconciliation_id}/review", response_model=ReconciliationRead)
async def reconciliation_review(reconciliation_id: UUID, lock: bool = False, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ReconciliationRead.model_validate(await service.review_reconciliation(db, actor, reconciliation_id, lock=lock))


@router.get("/providers", response_model=list[PaymentProviderRead])
async def providers(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [PaymentProviderRead.model_validate(r) for r in await service.list_providers(db, actor)]


@router.post("/providers", response_model=PaymentProviderRead, status_code=201)
async def create_provider(payload: PaymentProviderCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return PaymentProviderRead.model_validate(await service.create_provider(db, actor, payload))


@router.post("/payment-intents", response_model=PaymentIntentRead, status_code=201)
async def create_payment_intent(payload: PaymentIntentCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return PaymentIntentRead.model_validate(await service.create_payment_intent(db, actor, payload))
