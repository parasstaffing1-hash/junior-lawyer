from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.security import AuditChainHead, AuditOutcome, SecurityAuditEntry
from app.services.security.context import ActorContext
from app.services.security.crypto import privacy_hash


ZERO_HASH = "0" * 64


def _canonical_payload(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _canonical_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def compute_audit_hash(previous_hash: str, payload: dict, *, key: str | None = None) -> tuple[str, str]:
    message = previous_hash.encode("ascii") + b"|" + _canonical_payload(payload)
    if key:
        return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest(), "hmac-sha256-v1"
    return hashlib.sha256(message).hexdigest(), "sha256-chain-v1"


def _entry_payload(entry: SecurityAuditEntry | dict) -> dict:
    if isinstance(entry, dict):
        return entry
    return {
        "organization_id": str(entry.organization_id),
        "sequence": entry.sequence,
        "occurred_at": _canonical_datetime(entry.occurred_at),
        "actor_user_id": str(entry.actor_user_id) if entry.actor_user_id else None,
        "actor_membership_id": str(entry.actor_membership_id) if entry.actor_membership_id else None,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "outcome": entry.outcome.value,
        "reason": entry.reason,
        "request_id": entry.request_id,
        "ip_hash": entry.ip_hash,
        "user_agent_hash": entry.user_agent_hash,
        "metadata_json": entry.metadata_json,
    }


async def append_audit_event(
    db: AsyncSession,
    *,
    organization_id: UUID,
    action: str,
    resource_type: str,
    outcome: AuditOutcome,
    actor: ActorContext | None = None,
    resource_id: str | None = None,
    reason: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None,
) -> SecurityAuditEntry:
    head = await db.scalar(
        select(AuditChainHead)
        .where(AuditChainHead.organization_id == organization_id)
        .with_for_update()
    )
    if head is None:
        head = AuditChainHead(organization_id=organization_id, sequence=0, head_hash=ZERO_HASH)
        db.add(head)
        await db.flush()

    sequence = head.sequence + 1
    occurred_at = datetime.now(timezone.utc)
    payload = {
        "organization_id": str(organization_id),
        "sequence": sequence,
        "occurred_at": _canonical_datetime(occurred_at),
        "actor_user_id": str(actor.user_id) if actor else None,
        "actor_membership_id": str(actor.membership_id) if actor else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome.value,
        "reason": reason,
        "request_id": request_id,
        "ip_hash": privacy_hash(ip_address),
        "user_agent_hash": privacy_hash(user_agent),
        "metadata_json": metadata or {},
    }
    event_hash, signature_mode = compute_audit_hash(
        head.head_hash,
        payload,
        key=settings.security_audit_hmac_key,
    )
    entry = SecurityAuditEntry(
        organization_id=organization_id,
        sequence=sequence,
        occurred_at=occurred_at,
        actor_user_id=actor.user_id if actor else None,
        actor_membership_id=actor.membership_id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason=reason,
        request_id=request_id,
        ip_hash=payload["ip_hash"],
        user_agent_hash=payload["user_agent_hash"],
        metadata_json=metadata or {},
        previous_hash=head.head_hash,
        event_hash=event_hash,
        signature_mode=signature_mode,
    )
    db.add(entry)
    head.sequence = sequence
    head.head_hash = event_hash
    await db.flush()
    return entry


async def verify_audit_chain(db: AsyncSession, organization_id: UUID) -> dict:
    entries = list(
        (
            await db.scalars(
                select(SecurityAuditEntry)
                .where(SecurityAuditEntry.organization_id == organization_id)
                .order_by(SecurityAuditEntry.sequence)
            )
        ).all()
    )
    previous = ZERO_HASH
    signed = True
    expected_sequence = 1
    for entry in entries:
        if entry.sequence != expected_sequence:
            return {
                "valid": False,
                "checked_entries": expected_sequence - 1,
                "first_invalid_sequence": entry.sequence,
                "reason": "Audit sequence gap or reordering detected",
                "signed": signed,
            }
        if entry.previous_hash != previous:
            return {
                "valid": False,
                "checked_entries": expected_sequence - 1,
                "first_invalid_sequence": entry.sequence,
                "reason": "Previous-hash link mismatch",
                "signed": signed,
            }
        if entry.signature_mode.startswith("hmac") and not settings.security_audit_hmac_key:
            return {
                "valid": False,
                "checked_entries": expected_sequence - 1,
                "first_invalid_sequence": entry.sequence,
                "reason": "Audit HMAC key is unavailable for verification",
                "signed": True,
            }
        if not entry.signature_mode.startswith("hmac"):
            signed = False
        key = settings.security_audit_hmac_key if entry.signature_mode.startswith("hmac") else None
        expected_hash, _ = compute_audit_hash(previous, _entry_payload(entry), key=key)
        if not hmac.compare_digest(expected_hash, entry.event_hash):
            return {
                "valid": False,
                "checked_entries": expected_sequence - 1,
                "first_invalid_sequence": entry.sequence,
                "reason": "Audit event hash mismatch",
                "signed": signed,
            }
        previous = entry.event_hash
        expected_sequence += 1
    return {
        "valid": True,
        "checked_entries": len(entries),
        "first_invalid_sequence": None,
        "reason": None,
        "signed": signed and bool(entries),
    }
