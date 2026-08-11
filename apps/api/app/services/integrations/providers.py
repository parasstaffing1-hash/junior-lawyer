from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx

from app.models.integrations import IntegrationConnection, IntegrationProvider

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"
DOCUSIGN_DEFAULT_BASE_URL = "https://demo.docusign.net"

GOOGLE_GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GOOGLE_CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"


class IntegrationConfigurationError(RuntimeError):
    pass


class IntegrationProviderError(RuntimeError):
    pass


def canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def payload_sha256(payload: dict | bytes) -> str:
    raw = payload if isinstance(payload, bytes) else canonical_json_bytes(payload)
    return hashlib.sha256(raw).hexdigest()


def resolve_secret(reference: str) -> str:
    """Resolve secrets without persisting plaintext values in the database.

    Batch 25 ships an environment-variable resolver. Vault/cloud secret manager references remain
    explicit integration boundaries instead of being silently interpreted as plaintext.
    """
    reference = (reference or "").strip()
    if reference.startswith("env://"):
        name = reference[6:]
    elif reference.startswith("env:"):
        name = reference[4:]
    else:
        raise IntegrationConfigurationError(
            "Only env:// secret references are resolved by the built-in connector; configure a secret-manager adapter for other schemes"
        )
    if not name or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_" for ch in name):
        raise IntegrationConfigurationError("Invalid environment secret reference")
    value = os.getenv(name)
    if not value:
        raise IntegrationConfigurationError(f"Secret reference {reference} is not available in this runtime")
    return value


def _secret_map(connection: IntegrationConnection, secret_rows) -> dict[str, str]:
    return {row.secret_key: row.reference for row in secret_rows if row.connection_id == connection.id}


def require_secret(secret_refs: dict[str, str], key: str) -> str:
    reference = secret_refs.get(key)
    if not reference:
        raise IntegrationConfigurationError(f"Missing secret reference: {key}")
    return resolve_secret(reference)


def validate_nonsecret_config(config: dict) -> list[str]:
    forbidden_fragments = ("secret", "password", "private_key", "refresh_token", "access_token", "api_key")
    bad = [key for key in config if any(fragment in key.casefold() for fragment in forbidden_fragments)]
    return sorted(bad)


def build_google_authorization_url(*, client_id: str, redirect_uri: str, state: str, scopes: list[str]) -> str:
    query = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    })
    return f"{GOOGLE_AUTH_URL}?{query}"


async def google_access_token(connection: IntegrationConnection, secret_refs: dict[str, str]) -> str:
    client_id = str(connection.config_json.get("client_id") or "").strip()
    if not client_id:
        raise IntegrationConfigurationError("Google connection requires config.client_id")
    client_secret = require_secret(secret_refs, "client_secret")
    refresh_token = require_secret(secret_refs, "refresh_token")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if response.status_code >= 400:
        raise IntegrationProviderError(f"Google token refresh failed with HTTP {response.status_code}")
    token = response.json().get("access_token")
    if not token:
        raise IntegrationProviderError("Google token response did not contain an access token")
    return str(token)


async def gmail_send(connection: IntegrationConnection, secret_refs: dict[str, str], *, to: list[str], cc: list[str], bcc: list[str], subject: str, text_body: str, html_body: str | None, reply_to: str | None) -> dict:
    token = await google_access_token(connection, secret_refs)
    message = EmailMessage()
    sender = str(connection.config_json.get("sender_email") or "me")
    message["From"] = sender
    message["To"] = ", ".join(to)
    if cc: message["Cc"] = ", ".join(cc)
    if bcc: message["Bcc"] = ", ".join(bcc)
    if reply_to: message["Reply-To"] = reply_to
    message["Subject"] = subject
    message.set_content(text_body or "")
    if html_body:
        message.add_alternative(html_body, subtype="html")
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(GMAIL_SEND_URL, headers={"Authorization": f"Bearer {token}"}, json={"raw": raw})
    if response.status_code >= 400:
        raise IntegrationProviderError(f"Gmail send failed with HTTP {response.status_code}")
    return response.json()


async def calendar_create_event(connection: IntegrationConnection, secret_refs: dict[str, str], *, payload: dict, send_updates: str = "none") -> dict:
    token = await google_access_token(connection, secret_refs)
    calendar_id = str(connection.config_json.get("calendar_id") or "primary")
    url = CALENDAR_EVENTS_URL.format(calendar_id=quote(calendar_id, safe=""))
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(url, params={"sendUpdates": send_updates}, headers={"Authorization": f"Bearer {token}"}, json=payload)
    if response.status_code >= 400:
        raise IntegrationProviderError(f"Google Calendar event creation failed with HTTP {response.status_code}")
    return response.json()


async def razorpay_create_payment_link(connection: IntegrationConnection, secret_refs: dict[str, str], payload: dict) -> dict:
    key_id = str(connection.config_json.get("key_id") or "").strip()
    if not key_id:
        raise IntegrationConfigurationError("Razorpay connection requires config.key_id")
    key_secret = require_secret(secret_refs, "key_secret")
    async with httpx.AsyncClient(timeout=45, auth=(key_id, key_secret)) as client:
        response = await client.post(f"{RAZORPAY_BASE_URL}/payment_links", json=payload)
    if response.status_code >= 400:
        raise IntegrationProviderError(f"Razorpay payment-link creation failed with HTTP {response.status_code}")
    return response.json()


def verify_razorpay_signature(raw_body: bytes, received_signature: str, webhook_secret: str) -> bool:
    expected = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_signature or "")


def verify_docusign_signature(raw_body: bytes, received_signature: str, hmac_secret: str) -> bool:
    expected = base64.b64encode(hmac.new(hmac_secret.encode("utf-8"), raw_body, hashlib.sha256).digest()).decode("ascii")
    return hmac.compare_digest(expected, received_signature or "")


def verify_generic_signature(raw_body: bytes, received_signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    supplied = (received_signature or "").removeprefix("sha256=")
    return hmac.compare_digest(expected, supplied)


def build_docusign_envelope_payload(*, document_bytes: bytes, document_name: str, signer_name: str, signer_email: str, email_subject: str, status: str) -> dict:
    return {
        "emailSubject": email_subject,
        "documents": [{
            "documentBase64": base64.b64encode(document_bytes).decode("ascii"),
            "name": document_name,
            "fileExtension": Path(document_name).suffix.lstrip(".") or "pdf",
            "documentId": "1",
        }],
        "recipients": {
            "signers": [{"email": signer_email, "name": signer_name, "recipientId": "1", "routingOrder": "1"}]
        },
        "status": status,
    }


async def docusign_create_envelope(connection: IntegrationConnection, secret_refs: dict[str, str], *, payload: dict) -> dict:
    account_id = str(connection.config_json.get("account_id") or "").strip()
    if not account_id:
        raise IntegrationConfigurationError("DocuSign connection requires config.account_id")
    base_url = str(connection.config_json.get("base_url") or DOCUSIGN_DEFAULT_BASE_URL).rstrip("/")
    access_token = require_secret(secret_refs, "access_token")
    url = f"{base_url}/restapi/v2.1/accounts/{account_id}/envelopes"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, headers={"Authorization": f"Bearer {access_token}"}, json=payload)
    if response.status_code >= 400:
        raise IntegrationProviderError(f"DocuSign envelope creation failed with HTTP {response.status_code}")
    return response.json()


async def generic_webhook_send(*, url: str, event_type: str, payload: dict, secret: str | None, idempotency_key: str | None = None) -> dict:
    body = canonical_json_bytes(payload)
    headers = {"content-type": "application/json", "x-junior-lawyer-event": event_type}
    if idempotency_key:
        headers["idempotency-key"] = idempotency_key
    if secret:
        headers["x-junior-lawyer-signature"] = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, content=body, headers=headers)
    if response.status_code >= 400:
        raise IntegrationProviderError(f"Outbound webhook failed with HTTP {response.status_code}")
    try:
        response_json = response.json()
    except Exception:
        response_json = {}
    return {"status_code": response.status_code, "response_json": response_json}


@dataclass(frozen=True, slots=True)
class ProviderCatalog:
    provider: IntegrationProvider
    title: str
    description: str
    capabilities: list[str]
    required_config: list[str]
    optional_config: list[str]
    required_secrets: list[str]
    official_docs: list[str]


CATALOG = [
    ProviderCatalog(IntegrationProvider.GOOGLE_WORKSPACE, "Google Workspace", "Send Gmail messages and create Calendar events using OAuth 2.0 credentials provisioned by the firm.", ["gmail.send", "calendar.events.create"], ["client_id"], ["sender_email", "calendar_id"], ["client_secret", "refresh_token"], ["Gmail API messages.send", "Google Calendar events.insert", "Google OAuth 2.0 web-server flow"]),
    ProviderCatalog(IntegrationProvider.RAZORPAY, "Razorpay", "Create payment links and receive signed payment webhooks.", ["payment_links.create", "webhooks.receive"], ["key_id"], [], ["key_secret", "webhook_secret"], ["Razorpay Payment Links API", "Razorpay webhook signature validation"]),
    ProviderCatalog(IntegrationProvider.DOCUSIGN, "DocuSign eSignature", "Create envelopes from approved document versions and receive Connect status updates.", ["envelopes.create", "webhooks.receive"], ["account_id"], ["base_url"], ["access_token", "webhook_hmac_secret"], ["DocuSign eSignature envelopes", "DocuSign Connect HMAC"]),
    ProviderCatalog(IntegrationProvider.GENERIC_WEBHOOK, "Generic webhook", "Send or receive HMAC-signed JSON events to approved systems.", ["webhooks.send", "webhooks.receive"], ["allowed_hosts"], [], ["outbound_hmac_secret", "inbound_hmac_secret"], ["Internal connector contract"]),
    ProviderCatalog(IntegrationProvider.OFFICIAL_LEGAL_IMPORT, "Official legal-data import", "Ingest approved normalized exports from authoritative legal/court sources without CAPTCHA bypassing.", ["legal_data.import"], ["allowed_source_domains"], [], [], ["India Code / eCourts official-source boundary"]),
]


def provider_catalog() -> list[ProviderCatalog]:
    return CATALOG
