from __future__ import annotations

import hashlib
import hmac
import json
import ipaddress
import secrets
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_money import PaymentIntent, PaymentIntentStatus, PaymentProviderEvent, PaymentProviderKind
from app.models.collaboration import (
    DocumentVersion, ESignatureEnvelope, ESignatureEnvelopeStatus, ESignatureProvider,
    ESignatureSigner, ESignatureSignerStatus,
)
from app.models.integrations import (
    DeliveryStatus, IntegrationConnection, IntegrationDeliveryAttempt, IntegrationHealthCheck,
    IntegrationOAuthState, IntegrationProvider, IntegrationResourceMapping, IntegrationSecretReference,
    IntegrationStatus, IntegrationWebhookEndpoint, IntegrationWebhookEvent, WebhookEventStatus,
)
from app.models.security import AuditOutcome, DocumentAccessLevel, OrganizationRole
from app.schemas.integrations import (
    CalendarEventRequest, DocusignEnvelopeRequest, GmailSendRequest, IntegrationConnectionCreate,
    OfficialLegalImportRequest, OutboundWebhookRequest, PaymentLinkRequest, WebhookEndpointCreate,
)
from app.services.documents.storage import resolve_storage_key
from app.services.integrations import providers
from app.schemas.research import JudgmentImportRequest, StatuteImportRequest
from app.services.research.importer import import_judgment, import_statute
from urllib.parse import urlparse
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext
from app.services.security.permissions import decide_document_access

MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}
LEGAL_SEND_ROLES = MANAGER_ROLES | {OrganizationRole.LAWYER, OrganizationRole.JUNIOR, OrganizationRole.PARALEGAL}
PAYMENT_ROLES = MANAGER_ROLES | {OrganizationRole.BILLING}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _value(value) -> str:
    return getattr(value, "value", str(value))


def _mark_connected(connection: IntegrationConnection) -> None:
    connection.status = IntegrationStatus.CONNECTED
    connection.last_connected_at = utcnow()
    connection.last_error = None


def _require_role(actor: ActorContext, roles: set[OrganizationRole], message: str) -> None:
    if actor.role not in roles:
        raise HTTPException(403, message)


async def _audit(db: AsyncSession, actor: ActorContext, action: str, resource_type: str, resource_id, metadata: dict | None = None) -> None:
    await append_audit_event(
        db, organization_id=actor.organization_id, actor=actor, action=action,
        resource_type=resource_type, resource_id=str(resource_id), outcome=AuditOutcome.SUCCESS,
        metadata=metadata or {},
    )


async def get_connection(db: AsyncSession, actor: ActorContext, connection_id: UUID) -> IntegrationConnection:
    row = await db.get(IntegrationConnection, connection_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Integration connection not found")
    return row


async def connection_secrets(db: AsyncSession, connection_id: UUID) -> list[IntegrationSecretReference]:
    return list((await db.scalars(select(IntegrationSecretReference).where(IntegrationSecretReference.connection_id == connection_id))).all())


def catalog() -> list[dict]:
    return [
        {
            "provider": item.provider,
            "title": item.title,
            "description": item.description,
            "capabilities": item.capabilities,
            "required_config": item.required_config,
            "optional_config": item.optional_config,
            "required_secrets": item.required_secrets,
            "official_docs": item.official_docs,
        }
        for item in providers.provider_catalog()
    ]


async def create_connection(db: AsyncSession, actor: ActorContext, payload: IntegrationConnectionCreate) -> IntegrationConnection:
    _require_role(actor, MANAGER_ROLES, "Partner/admin access is required to configure integrations")
    bad = providers.validate_nonsecret_config(payload.config)
    if bad:
        raise HTTPException(422, f"Secret-like values must use secret references, not config_json: {', '.join(bad)}")
    for item in payload.secrets:
        if not item.reference.startswith(("env://", "env:")):
            raise HTTPException(422, "Built-in secret resolver accepts env:// references only; configure an external secret-manager adapter for other schemes")
    row = IntegrationConnection(
        organization_id=actor.organization_id,
        connection_key=payload.connection_key,
        display_name=payload.display_name,
        provider=payload.provider,
        status=IntegrationStatus.CONFIGURED,
        enabled=True,
        capabilities_json=payload.capabilities,
        config_json=payload.config,
        created_by_membership_id=actor.membership_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Integration connection key already exists") from exc
    for item in payload.secrets:
        db.add(IntegrationSecretReference(connection_id=row.id, secret_key=item.secret_key, reference=item.reference, required=item.required))
    await _audit(db, actor, "integration.connection.create", "integration_connection", row.id, {"provider": _value(payload.provider)})
    await db.commit(); await db.refresh(row)
    return row


async def list_connections(db: AsyncSession, actor: ActorContext) -> list[IntegrationConnection]:
    return list((await db.scalars(select(IntegrationConnection).where(IntegrationConnection.organization_id == actor.organization_id).order_by(IntegrationConnection.provider, IntegrationConnection.display_name))).all())


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    connections = await list_connections(db, actor)
    ids = [row.id for row in connections]
    health = list((await db.scalars(select(IntegrationHealthCheck).where(IntegrationHealthCheck.connection_id.in_(ids)).order_by(IntegrationHealthCheck.checked_at.desc()).limit(50))).all()) if ids else []
    latest: dict[UUID, IntegrationHealthCheck] = {}
    for row in health:
        latest.setdefault(row.connection_id, row)
    counts: dict[str, int] = {}
    for row in connections:
        counts[_value(row.provider)] = counts.get(_value(row.provider), 0) + 1
    return {
        "connections": connections,
        "health": list(latest.values()),
        "provider_counts": counts,
        "connected_count": sum(1 for row in connections if _value(row.status) == IntegrationStatus.CONNECTED.value),
        "degraded_count": sum(1 for row in connections if _value(row.status) == IntegrationStatus.DEGRADED.value),
    }


def _configuration_checks(connection: IntegrationConnection, secrets_rows: list[IntegrationSecretReference]) -> list[dict]:
    secret_keys = {row.secret_key for row in secrets_rows}
    config = connection.config_json or {}
    checks: list[dict] = []
    required_config: list[str] = []
    required_secrets: list[str] = []
    if _value(connection.provider) == IntegrationProvider.GOOGLE_WORKSPACE.value:
        required_config = ["client_id"]
        required_secrets = ["client_secret", "refresh_token"]
    elif _value(connection.provider) == IntegrationProvider.RAZORPAY.value:
        required_config = ["key_id"]
        required_secrets = ["key_secret"]
    elif _value(connection.provider) == IntegrationProvider.DOCUSIGN.value:
        required_config = ["account_id"]
        required_secrets = ["access_token"]
    elif _value(connection.provider) == IntegrationProvider.OFFICIAL_LEGAL_IMPORT.value:
        required_config = ["allowed_source_domains"]
    for key in required_config:
        checks.append({"key": f"config.{key}", "passed": bool(config.get(key)), "message": "Configured" if config.get(key) else "Missing"})
    for key in required_secrets:
        checks.append({"key": f"secret.{key}", "passed": key in secret_keys, "message": "Secret reference present" if key in secret_keys else "Missing secret reference"})
    for row in secrets_rows:
        try:
            providers.resolve_secret(row.reference)
            checks.append({"key": f"resolve.{row.secret_key}", "passed": True, "message": "Runtime secret resolved"})
        except Exception as exc:
            checks.append({"key": f"resolve.{row.secret_key}", "passed": not row.required, "message": str(exc)})
    return checks


async def test_connection(db: AsyncSession, actor: ActorContext, connection_id: UUID, *, live_probe: bool = False) -> dict:
    _require_role(actor, MANAGER_ROLES, "Partner/admin access is required to test integrations")
    connection = await get_connection(db, actor, connection_id)
    secret_rows = await connection_secrets(db, connection.id)
    checks = _configuration_checks(connection, secret_rows)
    started = time.perf_counter()
    error = None
    if live_probe and all(row["passed"] for row in checks):
        try:
            refs = {row.secret_key: row.reference for row in secret_rows}
            if _value(connection.provider) == IntegrationProvider.GOOGLE_WORKSPACE.value:
                await providers.google_access_token(connection, refs)
                checks.append({"key": "live.oauth_refresh", "passed": True, "message": "Google OAuth refresh succeeded"})
            elif _value(connection.provider) == IntegrationProvider.RAZORPAY.value:
                # Avoid creating financial resources in a connection test; successful secret resolution is the live boundary.
                checks.append({"key": "live.safe_probe", "passed": True, "message": "No mutating Razorpay probe performed; use staging Payment Link operation for live verification"})
            elif _value(connection.provider) == IntegrationProvider.DOCUSIGN.value:
                checks.append({"key": "live.safe_probe", "passed": True, "message": "No envelope created during health probe; use a draft envelope in staging for live verification"})
            else:
                checks.append({"key": "live.safe_probe", "passed": True, "message": "Configuration resolved; no mutating provider call performed"})
        except Exception as exc:
            error = str(exc)
            checks.append({"key": "live.provider", "passed": False, "message": error})
    all_passed = bool(checks) and all(row["passed"] for row in checks)
    provider_value = _value(connection.provider)
    genuinely_live = live_probe and provider_value == IntegrationProvider.GOOGLE_WORKSPACE.value and all_passed
    status = IntegrationStatus.CONNECTED if genuinely_live else (IntegrationStatus.CONFIGURED if all_passed else IntegrationStatus.DEGRADED)
    latency = round((time.perf_counter() - started) * 1000)
    connection.status = status
    connection.last_error = error
    if status == IntegrationStatus.CONNECTED:
        connection.last_connected_at = utcnow()
    check = IntegrationHealthCheck(connection_id=connection.id, status=status, checked_at=utcnow(), live_probe=live_probe, latency_ms=latency, checks_json=checks, error_message=error)
    db.add(check)
    await _audit(db, actor, "integration.connection.test", "integration_connection", connection.id, {"status": _value(status), "live_probe": live_probe})
    await db.commit(); await db.refresh(check)
    return {"connection_id": connection.id, "status": status, "live_probe": live_probe, "checks": checks, "latency_ms": latency, "error": error}


async def start_google_oauth(db: AsyncSession, actor: ActorContext, connection_id: UUID, *, redirect_uri: str, scopes: list[str]) -> dict:
    _require_role(actor, MANAGER_ROLES, "Partner/admin access is required to configure OAuth")
    connection = await get_connection(db, actor, connection_id)
    if _value(connection.provider) != IntegrationProvider.GOOGLE_WORKSPACE.value:
        raise HTTPException(422, "OAuth helper is available only for Google Workspace connections")
    client_id = str(connection.config_json.get("client_id") or "")
    if not client_id:
        raise HTTPException(422, "Google connection requires config.client_id")
    scopes = scopes or [providers.GOOGLE_GMAIL_SEND_SCOPE, providers.GOOGLE_CALENDAR_EVENTS_SCOPE]
    raw_state = secrets.token_urlsafe(32)
    expires = utcnow() + timedelta(minutes=10)
    row = IntegrationOAuthState(connection_id=connection.id, state_hash=hashlib.sha256(raw_state.encode()).hexdigest(), redirect_uri=redirect_uri, requested_scopes_json=scopes, expires_at=expires)
    db.add(row); await db.flush()
    url = providers.build_google_authorization_url(client_id=client_id, redirect_uri=redirect_uri, state=raw_state, scopes=scopes)
    await _audit(db, actor, "integration.oauth.start", "integration_connection", connection.id, {"provider": "google_workspace", "scopes": scopes})
    await db.commit()
    return {"authorization_url": url, "expires_at": expires, "note": "This helper creates the authorization request only. Persist the resulting refresh token in your external secret store and reference it as env://...; Junior Lawyer does not store OAuth refresh tokens in the database."}


async def _record_delivery(db: AsyncSession, actor: ActorContext, connection: IntegrationConnection, *, operation: str, request_payload: dict, external_id: str | None, external_url: str | None, metadata: dict, idempotency_key: str | None = None) -> IntegrationDeliveryAttempt:
    row = IntegrationDeliveryAttempt(organization_id=actor.organization_id, connection_id=connection.id, operation=operation, status=DeliveryStatus.SENT, idempotency_key=idempotency_key, request_sha256=providers.payload_sha256(request_payload), external_resource_id=external_id, external_url=external_url, response_metadata_json=metadata, attempted_at=utcnow(), finished_at=utcnow())
    db.add(row); await db.flush(); return row


async def _mapping(db: AsyncSession, connection: IntegrationConnection, *, internal_type: str | None, internal_id: str | None, external_type: str, external_id: str | None, external_url: str | None, metadata: dict | None = None) -> None:
    if not internal_type or not internal_id or not external_id:
        return
    existing = await db.scalar(select(IntegrationResourceMapping).where(IntegrationResourceMapping.connection_id == connection.id, IntegrationResourceMapping.internal_resource_type == internal_type, IntegrationResourceMapping.internal_resource_id == internal_id, IntegrationResourceMapping.external_resource_type == external_type))
    if existing:
        existing.external_resource_id = external_id; existing.external_url = external_url; existing.metadata_json = metadata or {}
    else:
        db.add(IntegrationResourceMapping(connection_id=connection.id, internal_resource_type=internal_type, internal_resource_id=internal_id, external_resource_type=external_type, external_resource_id=external_id, external_url=external_url, metadata_json=metadata or {}))


async def send_gmail(db: AsyncSession, actor: ActorContext, connection_id: UUID, payload: GmailSendRequest) -> dict:
    _require_role(actor, LEGAL_SEND_ROLES, "Legal workspace access is required to send email")
    connection = await get_connection(db, actor, connection_id)
    if _value(connection.provider) != IntegrationProvider.GOOGLE_WORKSPACE.value: raise HTTPException(422, "Connection is not Google Workspace")
    refs = {row.secret_key: row.reference for row in await connection_secrets(db, connection.id)}
    response = await providers.gmail_send(connection, refs, to=payload.to, cc=payload.cc, bcc=payload.bcc, subject=payload.subject, text_body=payload.text_body, html_body=payload.html_body, reply_to=payload.reply_to)
    _mark_connected(connection)
    external_id = response.get("id"); metadata = {"thread_id": response.get("threadId")}
    await _record_delivery(db, actor, connection, operation="gmail.send", request_payload=payload.model_dump(mode="json"), external_id=external_id, external_url=None, metadata=metadata)
    await _mapping(db, connection, internal_type=payload.internal_resource_type, internal_id=payload.internal_resource_id, external_type="gmail_message", external_id=external_id, external_url=None, metadata=metadata)
    await _audit(db, actor, "integration.gmail.send", "integration_connection", connection.id, {"message_id": external_id, "recipient_count": len(payload.to)+len(payload.cc)+len(payload.bcc)})
    await db.commit()
    return {"provider": connection.provider, "operation": "gmail.send", "external_resource_id": external_id, "external_url": None, "metadata": metadata}


async def create_calendar_event(db: AsyncSession, actor: ActorContext, connection_id: UUID, payload: CalendarEventRequest) -> dict:
    _require_role(actor, LEGAL_SEND_ROLES, "Legal workspace access is required to create calendar events")
    if payload.end <= payload.start: raise HTTPException(422, "Calendar event end must be after start")
    connection = await get_connection(db, actor, connection_id)
    if _value(connection.provider) != IntegrationProvider.GOOGLE_WORKSPACE.value: raise HTTPException(422, "Connection is not Google Workspace")
    refs = {row.secret_key: row.reference for row in await connection_secrets(db, connection.id)}
    event_payload = {"summary": payload.summary, "start": {"dateTime": payload.start.isoformat(), "timeZone": payload.timezone}, "end": {"dateTime": payload.end.isoformat(), "timeZone": payload.timezone}}
    if payload.description: event_payload["description"] = payload.description
    if payload.location: event_payload["location"] = payload.location
    if payload.attendees: event_payload["attendees"] = [{"email": email} for email in payload.attendees]
    response = await providers.calendar_create_event(connection, refs, payload=event_payload, send_updates=payload.send_updates)
    _mark_connected(connection)
    external_id = response.get("id"); url = response.get("htmlLink"); metadata = {"ical_uid": response.get("iCalUID"), "status": response.get("status")}
    await _record_delivery(db, actor, connection, operation="calendar.events.create", request_payload=event_payload, external_id=external_id, external_url=url, metadata=metadata)
    await _mapping(db, connection, internal_type=payload.internal_resource_type, internal_id=payload.internal_resource_id, external_type="calendar_event", external_id=external_id, external_url=url, metadata=metadata)
    await _audit(db, actor, "integration.calendar.event.create", "integration_connection", connection.id, {"event_id": external_id})
    await db.commit()
    return {"provider": connection.provider, "operation": "calendar.events.create", "external_resource_id": external_id, "external_url": url, "metadata": metadata}


async def create_payment_link(db: AsyncSession, actor: ActorContext, connection_id: UUID, payload: PaymentLinkRequest) -> dict:
    _require_role(actor, PAYMENT_ROLES, "Billing or partner/admin access is required to create payment links")
    connection = await get_connection(db, actor, connection_id)
    if _value(connection.provider) != IntegrationProvider.RAZORPAY.value: raise HTTPException(422, "Connection is not Razorpay")
    refs = {row.secret_key: row.reference for row in await connection_secrets(db, connection.id)}
    request_json: dict = {"amount": payload.amount_paise, "currency": payload.currency.upper(), "description": payload.description, "notify": {"sms": payload.notify_sms, "email": payload.notify_email}, "reminder_enable": True, "accept_partial": payload.allow_partial}
    if payload.reference_id: request_json["reference_id"] = payload.reference_id
    if payload.expire_by: request_json["expire_by"] = payload.expire_by
    customer = {k: v for k, v in {"name": payload.customer_name, "email": payload.customer_email, "contact": payload.customer_phone}.items() if v}
    if customer: request_json["customer"] = customer
    response = await providers.razorpay_create_payment_link(connection, refs, request_json)
    _mark_connected(connection)
    external_id = response.get("id"); url = response.get("short_url"); metadata = {"status": response.get("status"), "amount": response.get("amount"), "currency": response.get("currency")}
    await _record_delivery(db, actor, connection, operation="razorpay.payment_link.create", request_payload=request_json, external_id=external_id, external_url=url, metadata=metadata, idempotency_key=payload.reference_id)
    await _mapping(db, connection, internal_type=payload.internal_resource_type, internal_id=payload.internal_resource_id, external_type="razorpay_payment_link", external_id=external_id, external_url=url, metadata=metadata)
    await _audit(db, actor, "integration.razorpay.payment_link.create", "integration_connection", connection.id, {"payment_link_id": external_id})
    await db.commit()
    return {"provider": connection.provider, "operation": "razorpay.payment_link.create", "external_resource_id": external_id, "external_url": url, "metadata": metadata}


async def create_docusign_envelope(db: AsyncSession, actor: ActorContext, connection_id: UUID, payload: DocusignEnvelopeRequest) -> dict:
    _require_role(actor, LEGAL_SEND_ROLES, "Legal workspace access is required to send documents for signature")
    connection = await get_connection(db, actor, connection_id)
    if _value(connection.provider) != IntegrationProvider.DOCUSIGN.value: raise HTTPException(422, "Connection is not DocuSign")
    version = await db.get(DocumentVersion, payload.document_version_id)
    if not version: raise HTTPException(404, "Document version not found")
    decision = await decide_document_access(db, actor, version.document_id, required=DocumentAccessLevel.DOWNLOAD)
    if not decision.allowed: raise HTTPException(403, decision.reason)
    file_path = resolve_storage_key(version.storage_key)
    document_bytes = file_path.read_bytes()
    refs = {row.secret_key: row.reference for row in await connection_secrets(db, connection.id)}
    envelope_payload = providers.build_docusign_envelope_payload(document_bytes=document_bytes, document_name=payload.document_name or version.filename, signer_name=payload.signer_name, signer_email=payload.signer_email, email_subject=payload.email_subject, status=payload.status)
    response = await providers.docusign_create_envelope(connection, refs, payload=envelope_payload)
    _mark_connected(connection)
    external_id = response.get("envelopeId"); metadata = {"status": response.get("status"), "status_date_time": response.get("statusDateTime")}
    envelope = ESignatureEnvelope(organization_id=actor.organization_id, document_id=version.document_id, document_version_id=version.id, matter_id=version.matter_id, provider=ESignatureProvider.DOCUSIGN, status=ESignatureEnvelopeStatus.SENT if payload.status == "sent" else ESignatureEnvelopeStatus.DRAFT, title=payload.email_subject, provider_reference=external_id, created_by_user_id=actor.user_id, sent_at=utcnow() if payload.status == "sent" else None, metadata_json={"connection_id": str(connection.id)})
    db.add(envelope); await db.flush()
    db.add(ESignatureSigner(envelope_id=envelope.id, name=payload.signer_name, email=payload.signer_email, signing_order=1, status=ESignatureSignerStatus.SENT if payload.status == "sent" else ESignatureSignerStatus.PENDING))
    await _record_delivery(db, actor, connection, operation="docusign.envelope.create", request_payload={"document_sha256": version.sha256, "signer_email_hash": hashlib.sha256(payload.signer_email.casefold().encode()).hexdigest(), "status": payload.status}, external_id=external_id, external_url=None, metadata=metadata)
    await _mapping(db, connection, internal_type=payload.internal_resource_type, internal_id=payload.internal_resource_id or str(version.id), external_type="docusign_envelope", external_id=external_id, external_url=None, metadata={"local_envelope_id": str(envelope.id)})
    await _audit(db, actor, "integration.docusign.envelope.create", "esignature_envelope", envelope.id, {"provider_reference": external_id})
    await db.commit()
    return {"provider": connection.provider, "operation": "docusign.envelope.create", "external_resource_id": external_id, "external_url": None, "metadata": {**metadata, "local_envelope_id": str(envelope.id)}}


def _validate_outbound_webhook_url(connection: IntegrationConnection, url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise HTTPException(422, "Outbound webhook URLs must use HTTPS and include a hostname")
    host = parsed.hostname.casefold().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise HTTPException(422, "Localhost/local-network webhook hosts are not allowed")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
        raise HTTPException(422, "Private or reserved IP webhook targets are not allowed")
    raw_allowed = connection.config_json.get("allowed_hosts") or []
    if isinstance(raw_allowed, str):
        raw_allowed = [part.strip() for part in raw_allowed.split(",") if part.strip()]
    allowed = {str(item).casefold().strip().rstrip(".") for item in raw_allowed if str(item).strip()}
    if not allowed:
        raise HTTPException(422, "Generic webhook connection requires an explicit allowed_hosts list")
    if not any(host == item or host.endswith("." + item) for item in allowed):
        raise HTTPException(403, "Outbound webhook target is not on this connection's allowlist")
    return host


async def send_outbound_webhook(db: AsyncSession, actor: ActorContext, connection_id: UUID, payload: OutboundWebhookRequest) -> dict:
    _require_role(actor, MANAGER_ROLES, "Partner/admin access is required to send arbitrary integration webhooks")
    connection = await get_connection(db, actor, connection_id)
    if _value(connection.provider) != IntegrationProvider.GENERIC_WEBHOOK.value: raise HTTPException(422, "Connection is not a generic webhook connector")
    _validate_outbound_webhook_url(connection, payload.url)
    refs = {row.secret_key: row.reference for row in await connection_secrets(db, connection.id)}
    secret = providers.resolve_secret(refs["outbound_hmac_secret"]) if refs.get("outbound_hmac_secret") else None
    response = await providers.generic_webhook_send(url=payload.url, event_type=payload.event_type, payload=payload.payload, secret=secret, idempotency_key=payload.idempotency_key)
    _mark_connected(connection)
    await _record_delivery(db, actor, connection, operation="webhook.send", request_payload=payload.payload, external_id=None, external_url=payload.url, metadata={"status_code": response["status_code"]}, idempotency_key=payload.idempotency_key)
    await _audit(db, actor, "integration.webhook.send", "integration_connection", connection.id, {"event_type": payload.event_type, "status_code": response["status_code"]})
    await db.commit()
    return {"provider": connection.provider, "operation": "webhook.send", "external_resource_id": None, "external_url": payload.url, "metadata": response}


async def import_official_legal_data(db: AsyncSession, actor: ActorContext, connection_id: UUID, payload: OfficialLegalImportRequest) -> dict:
    _require_role(actor, MANAGER_ROLES, "Partner/admin access is required to import authoritative legal data")
    connection = await get_connection(db, actor, connection_id)
    if _value(connection.provider) != IntegrationProvider.OFFICIAL_LEGAL_IMPORT.value:
        raise HTTPException(422, "Connection is not an official legal-data import connector")
    allowed = {str(item).casefold().strip() for item in (connection.config_json.get("allowed_source_domains") or []) if str(item).strip()}
    host = (urlparse(payload.source_url).hostname or "").casefold()
    if not host or not any(host == domain or host.endswith("." + domain) for domain in allowed):
        raise HTTPException(422, "Source URL host is not allowlisted for this connector")
    if payload.source_sha256:
        actual = providers.payload_sha256(payload.payload)
        if not hmac.compare_digest(actual.casefold(), payload.source_sha256.casefold()):
            raise HTTPException(422, "Provided source SHA-256 does not match normalized payload")
    normalized = dict(payload.payload)
    _mark_connected(connection)
    normalized["source_url"] = payload.source_url
    if payload.feed_id:
        from app.schemas.legal_data import LegalDataManifest, LegalDataManifestItem
        from app.models.legal_data_ops import LegalDataRunTrigger
        from app.services.legal_data import service as legal_data_service
        feed = await legal_data_service.get_feed(db, actor, payload.feed_id)
        if feed.connection_id and feed.connection_id != connection.id:
            raise HTTPException(422, "Legal-data feed is bound to a different integration connection")
        detail = await legal_data_service.ingest_manifest(
            db, actor, feed.id,
            LegalDataManifest(
                source_label=f"integration:{connection.name}",
                items=[LegalDataManifestItem(kind=payload.kind, source_url=payload.source_url, payload=payload.payload, source_sha256=payload.source_sha256)],
                metadata={"integration_connection_id": str(connection.id)},
            ),
            trigger=LegalDataRunTrigger.INTEGRATION,
        )
        run = detail["run"]
        return {"provider": connection.provider, "operation": f"legal_import.{payload.kind}", "external_resource_id": str(run.id), "external_url": payload.source_url, "metadata": {"source_host": host, "legal_data_run_id": str(run.id), "duplicate_manifest": detail.get("duplicate_manifest", False)}}
    if payload.kind == "statute":
        record = await import_statute(db, StatuteImportRequest.model_validate(normalized))
        external_id = str(record.id); external_type = "statute"
    else:
        record = await import_judgment(db, JudgmentImportRequest.model_validate(normalized))
        external_id = str(record.id); external_type = "judgment"
    await _record_delivery(db, actor, connection, operation=f"legal_import.{payload.kind}", request_payload={"source_url": payload.source_url, "source_sha256": payload.source_sha256, "external_id": external_id}, external_id=external_id, external_url=payload.source_url, metadata={"source_host": host})
    await _audit(db, actor, "integration.legal_import", external_type, external_id, {"source_host": host})
    await db.commit()
    return {"provider": connection.provider, "operation": f"legal_import.{payload.kind}", "external_resource_id": external_id, "external_url": payload.source_url, "metadata": {"source_host": host}}


async def create_webhook_endpoint(db: AsyncSession, actor: ActorContext, payload: WebhookEndpointCreate) -> IntegrationWebhookEndpoint:
    _require_role(actor, MANAGER_ROLES, "Partner/admin access is required to configure webhooks")
    connection = await get_connection(db, actor, payload.connection_id)
    if payload.signing_secret_reference and not payload.signing_secret_reference.startswith(("env://", "env:")):
        raise HTTPException(422, "Built-in webhook secret resolver accepts env:// references only")
    row = IntegrationWebhookEndpoint(organization_id=actor.organization_id, connection_id=connection.id, endpoint_key=payload.endpoint_key, signing_secret_reference=payload.signing_secret_reference, enabled=True, event_types_json=payload.event_types, metadata_json={})
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "Webhook endpoint key already exists") from exc
    await _audit(db, actor, "integration.webhook_endpoint.create", "integration_webhook_endpoint", row.id, {"provider": _value(connection.provider)})
    await db.commit(); await db.refresh(row); return row


async def list_webhook_endpoints(db: AsyncSession, actor: ActorContext) -> list[IntegrationWebhookEndpoint]:
    return list((await db.scalars(select(IntegrationWebhookEndpoint).where(IntegrationWebhookEndpoint.organization_id == actor.organization_id).order_by(IntegrationWebhookEndpoint.created_at.desc()))).all())


def _normalize_webhook(provider: str, headers: dict[str, str], payload: dict, body_hash: str) -> tuple[str, str, dict]:
    if provider == IntegrationProvider.RAZORPAY.value:
        event_type = str(payload.get("event") or "unknown")
        event_id = headers.get("x-razorpay-event-id") or body_hash
        entities = payload.get("payload") or {}
        ids = {}
        for key in ("payment", "payment_link", "order", "invoice", "refund"):
            entity = ((entities.get(key) or {}).get("entity") or {}) if isinstance(entities, dict) else {}
            if entity.get("id"): ids[key] = entity.get("id")
        return event_id, event_type, {"entity_ids": ids, "created_at": payload.get("created_at")}
    if provider == IntegrationProvider.DOCUSIGN.value:
        data = payload.get("data") or payload
        envelope_id = data.get("envelopeId") or data.get("envelope_id") or payload.get("envelopeId")
        status = data.get("envelopeSummary", {}).get("status") if isinstance(data.get("envelopeSummary"), dict) else data.get("status")
        return str(payload.get("eventId") or envelope_id or body_hash), str(payload.get("event") or status or "docusign.connect"), {"envelope_id": envelope_id, "status": status}
    return str(headers.get("x-event-id") or headers.get("idempotency-key") or body_hash), str(headers.get("x-junior-lawyer-event") or payload.get("event") or "webhook.event"), {"keys": sorted(payload.keys())[:30]}


async def _apply_verified_webhook(db: AsyncSession, connection: IntegrationConnection, *, provider: str, event_type: str, external_id: str, normalized: dict, body_hash: str) -> None:
    if provider == IntegrationProvider.DOCUSIGN.value:
        envelope_id = normalized.get("envelope_id")
        status = str(normalized.get("status") or "").casefold()
        if envelope_id:
            envelope = await db.scalar(select(ESignatureEnvelope).where(ESignatureEnvelope.provider_reference == str(envelope_id), ESignatureEnvelope.organization_id == connection.organization_id))
            if envelope:
                mapping = {"sent": ESignatureEnvelopeStatus.SENT, "delivered": ESignatureEnvelopeStatus.VIEWED, "viewed": ESignatureEnvelopeStatus.VIEWED, "completed": ESignatureEnvelopeStatus.COMPLETED, "declined": ESignatureEnvelopeStatus.DECLINED, "voided": ESignatureEnvelopeStatus.VOIDED}
                if status in mapping:
                    envelope.status = mapping[status]
                    if status == "completed": envelope.completed_at = utcnow()
    if provider == IntegrationProvider.RAZORPAY.value:
        link_id = (normalized.get("entity_ids") or {}).get("payment_link")
        if not link_id:
            return
        mapping = await db.scalar(select(IntegrationResourceMapping).where(IntegrationResourceMapping.connection_id == connection.id, IntegrationResourceMapping.external_resource_type == "razorpay_payment_link", IntegrationResourceMapping.external_resource_id == str(link_id)))
        if mapping and mapping.internal_resource_type == "payment_intent":
            try: intent_id = UUID(mapping.internal_resource_id)
            except ValueError: return
            intent = await db.get(PaymentIntent, intent_id)
            if intent and intent.organization_id == connection.organization_id:
                event = event_type.casefold()
                if event.endswith(".paid"): intent.status = PaymentIntentStatus.SUCCEEDED
                elif event.endswith(".partially_paid"): intent.status = PaymentIntentStatus.PENDING
                elif event.endswith(".expired"): intent.status = PaymentIntentStatus.EXPIRED
                elif event.endswith(".cancelled"): intent.status = PaymentIntentStatus.CANCELLED
                intent.provider_reference = str(link_id)
                exists = await db.scalar(select(PaymentProviderEvent).where(PaymentProviderEvent.provider == PaymentProviderKind.RAZORPAY, PaymentProviderEvent.provider_event_id == external_id))
                if not exists:
                    db.add(PaymentProviderEvent(organization_id=connection.organization_id, payment_intent_id=intent.id, provider=PaymentProviderKind.RAZORPAY, provider_event_id=external_id, event_type=event_type, payload_hash=body_hash, received_at=utcnow(), metadata_json=normalized))


async def receive_webhook(db: AsyncSession, *, endpoint_key: str, raw_body: bytes, headers: dict[str, str]) -> IntegrationWebhookEvent:
    endpoint = await db.scalar(select(IntegrationWebhookEndpoint).where(IntegrationWebhookEndpoint.endpoint_key == endpoint_key, IntegrationWebhookEndpoint.enabled.is_(True)))
    if not endpoint: raise HTTPException(404, "Webhook endpoint not found")
    connection = await db.get(IntegrationConnection, endpoint.connection_id)
    if not connection or not connection.enabled: raise HTTPException(404, "Webhook connection is disabled")
    body_hash = hashlib.sha256(raw_body).hexdigest()
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        if not isinstance(payload, dict): payload = {"value_type": type(payload).__name__}
    except Exception:
        payload = {}
    secret = providers.resolve_secret(endpoint.signing_secret_reference) if endpoint.signing_secret_reference else None
    provider = _value(connection.provider)
    if provider == IntegrationProvider.RAZORPAY.value:
        valid = bool(secret) and providers.verify_razorpay_signature(raw_body, headers.get("x-razorpay-signature", ""), secret)
    elif provider == IntegrationProvider.DOCUSIGN.value:
        signature = headers.get("x-docusign-signature-1", "")
        valid = bool(secret) and providers.verify_docusign_signature(raw_body, signature, secret)
    elif provider == IntegrationProvider.GENERIC_WEBHOOK.value:
        valid = (secret is None) or providers.verify_generic_signature(raw_body, headers.get("x-junior-lawyer-signature", ""), secret)
    else:
        valid = secret is None
    external_id, event_type, normalized = _normalize_webhook(provider, headers, payload, body_hash)
    if endpoint.event_types_json and event_type not in endpoint.event_types_json:
        valid = False
        normalized["rejection_reason"] = "event_type_not_allowlisted"
    existing = await db.scalar(select(IntegrationWebhookEvent).where(IntegrationWebhookEvent.endpoint_id == endpoint.id, IntegrationWebhookEvent.external_event_id == external_id))
    if existing: return existing
    row = IntegrationWebhookEvent(endpoint_id=endpoint.id, external_event_id=external_id, event_type=event_type, status=WebhookEventStatus.VERIFIED if valid else WebhookEventStatus.REJECTED, body_sha256=body_hash, signature_valid=valid, normalized_payload_json=normalized, received_at=utcnow(), processed_at=None, error_message=None if valid else "Webhook signature or allowlist validation failed")
    db.add(row); await db.flush()
    if valid:
        await _apply_verified_webhook(db, connection, provider=provider, event_type=event_type, external_id=external_id, normalized=normalized, body_hash=body_hash)
        row.status = WebhookEventStatus.PROCESSED
        row.processed_at = utcnow()
    await db.commit(); await db.refresh(row)
    if not valid: raise HTTPException(401, "Webhook signature validation failed")
    return row
