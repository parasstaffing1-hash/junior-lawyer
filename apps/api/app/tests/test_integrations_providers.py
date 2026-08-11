import base64
import hashlib
import hmac
import os

import pytest

from app.models.integrations import IntegrationProvider
from app.services.integrations.providers import (
    build_docusign_envelope_payload,
    build_google_authorization_url,
    payload_sha256,
    provider_catalog,
    resolve_secret,
    validate_nonsecret_config,
    verify_docusign_signature,
    verify_generic_signature,
    verify_razorpay_signature,
)


def test_secret_resolver_only_accepts_references(monkeypatch):
    monkeypatch.setenv("JL_TEST_SECRET", "super-secret")
    assert resolve_secret("env://JL_TEST_SECRET") == "super-secret"
    with pytest.raises(Exception):
        resolve_secret("super-secret")


def test_nonsecret_config_rejects_plain_tokens():
    assert validate_nonsecret_config({"client_id": "abc", "refresh_token": "plaintext"}) == ["refresh_token"]
    assert validate_nonsecret_config({"client_id": "abc", "calendar_id": "primary"}) == []


def test_google_authorization_url_uses_offline_consent_and_scopes():
    url = build_google_authorization_url(client_id="client", redirect_uri="https://example.test/cb", state="state123", scopes=["scope.one", "scope.two"])
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "state=state123" in url
    assert "scope.one" in url


def test_razorpay_hmac_uses_raw_body():
    body = b'{"event":"payment.captured","amount":5000}'
    secret = "webhook-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_razorpay_signature(body, signature, secret)
    assert not verify_razorpay_signature(body + b" ", signature, secret)


def test_docusign_hmac_base64():
    body = b'{"event":"envelope-completed"}'
    secret = "connect-secret"
    signature = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    assert verify_docusign_signature(body, signature, secret)
    assert not verify_docusign_signature(b"changed", signature, secret)


def test_generic_webhook_accepts_sha256_prefix():
    body = b'{"hello":"world"}'
    secret = "shared"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_generic_signature(body, signature, secret)


def test_docusign_envelope_payload_has_document_and_signer():
    payload = build_docusign_envelope_payload(document_bytes=b"pdf", document_name="Agreement.pdf", signer_name="Asha", signer_email="asha@example.com", email_subject="Please sign", status="sent")
    assert payload["documents"][0]["documentId"] == "1"
    assert payload["recipients"]["signers"][0]["email"] == "asha@example.com"
    assert payload["status"] == "sent"


def test_provider_catalog_contains_real_boundaries():
    providers = {row.provider for row in provider_catalog()}
    assert IntegrationProvider.GOOGLE_WORKSPACE in providers
    assert IntegrationProvider.RAZORPAY in providers
    assert IntegrationProvider.DOCUSIGN in providers
    assert IntegrationProvider.OFFICIAL_LEGAL_IMPORT in providers


def test_payload_hash_stable():
    assert payload_sha256({"a": 1, "b": 2}) == payload_sha256({"b": 2, "a": 1})


def test_outbound_webhook_allowlist_blocks_ssrf_targets():
    from fastapi import HTTPException
    from app.models.integrations import IntegrationConnection
    from app.services.integrations.service import _validate_outbound_webhook_url

    connection = IntegrationConnection(config_json={"allowed_hosts": ["hooks.example.com"]})
    assert _validate_outbound_webhook_url(connection, "https://hooks.example.com/events") == "hooks.example.com"
    assert _validate_outbound_webhook_url(connection, "https://sub.hooks.example.com/events") == "sub.hooks.example.com"
    for url in [
        "http://hooks.example.com/events",
        "https://localhost/events",
        "https://127.0.0.1/events",
        "https://169.254.169.254/latest/meta-data",
        "https://evil.example.com/events",
    ]:
        with pytest.raises(HTTPException):
            _validate_outbound_webhook_url(connection, url)


def test_generic_webhook_catalog_requires_allowlist():
    item = next(row for row in provider_catalog() if row.provider == IntegrationProvider.GENERIC_WEBHOOK)
    assert "allowed_hosts" in item.required_config
