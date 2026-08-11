from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.integrations import (
    CalendarEventRequest, ConnectionTestRequest, ConnectionTestResult, DeliveryResult,
    DocusignEnvelopeRequest, GmailSendRequest, IntegrationCatalogItem, IntegrationConnectionCreate,
    IntegrationConnectionRead, IntegrationDashboard, OAuthStartRequest, OAuthStartResult,
    OfficialLegalImportRequest, OutboundWebhookRequest, PaymentLinkRequest, WebhookEndpointCreate, WebhookEndpointRead,
    WebhookEventRead,
)
from app.services.integrations import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/catalog", response_model=list[IntegrationCatalogItem])
async def catalog(actor: ActorContext = Depends(require_actor)):
    return service.catalog()


@router.get("/dashboard", response_model=IntegrationDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.dashboard(db, actor)


@router.get("", response_model=list[IntegrationConnectionRead])
async def connections(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_connections(db, actor)


@router.post("", response_model=IntegrationConnectionRead, status_code=201)
async def create_connection(payload: IntegrationConnectionCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_connection(db, actor, payload)


@router.post("/{connection_id}/test", response_model=ConnectionTestResult)
async def test_connection(connection_id: UUID, payload: ConnectionTestRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.test_connection(db, actor, connection_id, live_probe=payload.live_probe)


@router.post("/{connection_id}/google/oauth/start", response_model=OAuthStartResult)
async def google_oauth_start(connection_id: UUID, payload: OAuthStartRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.start_google_oauth(db, actor, connection_id, redirect_uri=payload.redirect_uri, scopes=payload.scopes)


@router.post("/{connection_id}/gmail/send", response_model=DeliveryResult)
async def gmail_send(connection_id: UUID, payload: GmailSendRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.send_gmail(db, actor, connection_id, payload)


@router.post("/{connection_id}/calendar/events", response_model=DeliveryResult)
async def calendar_event(connection_id: UUID, payload: CalendarEventRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_calendar_event(db, actor, connection_id, payload)


@router.post("/{connection_id}/razorpay/payment-links", response_model=DeliveryResult)
async def payment_link(connection_id: UUID, payload: PaymentLinkRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_payment_link(db, actor, connection_id, payload)


@router.post("/{connection_id}/docusign/envelopes", response_model=DeliveryResult)
async def docusign_envelope(connection_id: UUID, payload: DocusignEnvelopeRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_docusign_envelope(db, actor, connection_id, payload)


@router.post("/{connection_id}/legal-import", response_model=DeliveryResult)
async def official_legal_import(connection_id: UUID, payload: OfficialLegalImportRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.import_official_legal_data(db, actor, connection_id, payload)


@router.post("/{connection_id}/webhooks/outbound", response_model=DeliveryResult)
async def outbound_webhook(connection_id: UUID, payload: OutboundWebhookRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.send_outbound_webhook(db, actor, connection_id, payload)


@router.get("/webhook-endpoints", response_model=list[WebhookEndpointRead])
async def webhook_endpoints(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_webhook_endpoints(db, actor)


@router.post("/webhook-endpoints", response_model=WebhookEndpointRead, status_code=201)
async def create_webhook_endpoint(payload: WebhookEndpointCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_webhook_endpoint(db, actor, payload)


@router.post("/webhooks/{endpoint_key}", response_model=WebhookEventRead)
async def inbound_webhook(endpoint_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    headers = {key.casefold(): value for key, value in request.headers.items()}
    return await service.receive_webhook(db, endpoint_key=endpoint_key, raw_body=raw, headers=headers)
