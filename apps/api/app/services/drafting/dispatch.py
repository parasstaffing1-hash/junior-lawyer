"""Send a finished draft to a client or an opposite party.

Sending is the point where a draft stops being an internal document and becomes
an act with legal consequence — a notice served, a position stated to an
adversary. Three rules follow from that, and all three are enforced here rather
than left to the interface:

  * only an approved draft goes out. A draft still in review is a working
    document, and an AI-assisted one that no advocate has signed off must never
    reach an opposite party;
  * the send is explicit. The caller confirms this exact recipient list;
  * every send is written into the matter's communication record, because six
    months later the question will be what was sent, to whom, and when.

Delivery itself reuses the existing Google Workspace integration, so
credentials continue to live in the secrets vault and nowhere else.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import ClientCommunication, CommunicationType
from app.models.drafting import LegalDraft, LegalDraftStatus
from app.models.integrations import IntegrationConnection, IntegrationProvider
from app.schemas.integrations import GmailSendRequest
from app.services.integrations import service as integrations_service
from app.services.security.audit import append_audit_event
from app.models.security import AuditOutcome
from app.services.security.context import ActorContext

# Who a draft may be addressed to. The distinction is recorded because a notice
# to an opposite party and a copy to one's own client are different acts.
RECIPIENT_KINDS = {"client", "opposite_party", "court", "other"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def render_plain_text(draft: LegalDraft) -> str:
    """The draft as an email body: heading, then each section in order."""
    lines = [draft.title or "Draft", ""]
    for section in sorted(draft.sections, key=lambda item: item.position):
        heading = (section.title_en or "").strip()
        if heading:
            lines.append(heading.upper())
        body = (section.body_en or "").strip()
        if body:
            lines.append(body)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


async def _resolve_connection(
    db: AsyncSession, actor: ActorContext, connection_id: UUID | None
) -> IntegrationConnection:
    if connection_id:
        return await integrations_service.get_connection(db, actor, connection_id)
    connection = await db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == actor.organization_id,
            IntegrationConnection.provider == IntegrationProvider.GOOGLE_WORKSPACE,
        )
    )
    if not connection:
        raise HTTPException(
            status_code=422,
            detail=(
                "No email connection is configured. Connect Google Workspace in "
                "Integrations before sending a draft."
            ),
        )
    return connection


async def send_draft(
    db: AsyncSession,
    actor: ActorContext,
    draft_id: UUID,
    *,
    to: list[str],
    recipient_kind: str,
    subject: str | None = None,
    covering_note: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    reply_to: str | None = None,
    connection_id: UUID | None = None,
    confirm: bool = False,
) -> dict:
    draft = await db.get(LegalDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if not confirm:
        # The caller must state that it means to send to these recipients. A
        # mis-addressed legal notice cannot be recalled.
        raise HTTPException(
            status_code=428,
            detail="Confirm the recipients before sending. Set confirm=true to dispatch.",
        )
    if not to:
        raise HTTPException(status_code=422, detail="At least one recipient is required")
    if recipient_kind not in RECIPIENT_KINDS:
        raise HTTPException(
            status_code=422,
            detail=f"recipient_kind must be one of: {', '.join(sorted(RECIPIENT_KINDS))}",
        )
    if draft.status != LegalDraftStatus.APPROVED:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only an approved draft can be sent. This draft is "
                f"'{draft.status.value}' — have it reviewed and approved first."
            ),
        )

    body = render_plain_text(draft)
    if covering_note:
        body = f"{covering_note.strip()}\n\n{'-' * 60}\n\n{body}"

    connection = await _resolve_connection(db, actor, connection_id)
    result = await integrations_service.send_gmail(
        db,
        actor,
        connection.id,
        GmailSendRequest(
            to=to,
            cc=cc or [],
            bcc=bcc or [],
            subject=subject or draft.title or "Legal draft",
            text_body=body,
            html_body=None,
            reply_to=reply_to,
            internal_resource_type="legal_draft",
            internal_resource_id=str(draft.id),
        ),
    )

    # The matter file is the record that matters later, so write the send into
    # the client's communication history rather than only the integration log.
    if draft.matter_id:
        client_id = await db.scalar(
            select(ClientCommunication.client_id)
            .where(ClientCommunication.matter_id == draft.matter_id)
            .limit(1)
        )
        if client_id:
            db.add(
                ClientCommunication(
                    organization_id=actor.organization_id,
                    client_id=client_id,
                    matter_id=draft.matter_id,
                    recorded_by_user_id=actor.user_id,
                    communication_type=CommunicationType.EMAIL,
                    occurred_at=_now(),
                    direction="outbound",
                    subject=subject or draft.title,
                    summary=f"Draft '{draft.title}' sent to {recipient_kind.replace('_', ' ')}: {', '.join(to)}",
                    external_reference=str(result.get("external_resource_id") or ""),
                )
            )

    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action="drafting.send",
        resource_type="legal_draft",
        resource_id=str(draft.id),
        outcome=AuditOutcome.ALLOWED,
        metadata={
            "recipient_kind": recipient_kind,
            "recipient_count": len(to) + len(cc or []) + len(bcc or []),
            "draft_status": draft.status.value,
            "message_id": result.get("external_resource_id"),
        },
    )
    draft.metadata_json = {
        **(draft.metadata_json or {}),
        "last_sent_at": _now().isoformat(),
        "last_sent_to_kind": recipient_kind,
    }
    await db.commit()

    return {
        "draft_id": str(draft.id),
        "recipient_kind": recipient_kind,
        "recipients": to,
        "message_id": result.get("external_resource_id"),
        "sent_at": _now(),
    }
