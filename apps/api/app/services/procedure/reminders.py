"""Delivering the diary: WhatsApp and email.

A lawyer between hearings will not open a browser. They will open WhatsApp,
which they are in forty times a day. So the reminder goes to them rather than
waiting to be fetched, and the web app becomes the back office.

WhatsApp uses the Meta Cloud API. Two constraints shape this code:

  * outside a 24-hour customer-service window, Meta only permits a
    pre-approved template message, not free text. A nightly digest is always
    outside that window, so `template_name` must be configured and approved.
    Sending free text instead fails at Meta with an unhelpful error, so this
    module refuses before the request leaves;
  * delivery is best-effort per recipient. One lawyer's bad number must not
    stop the rest of the firm's reminders, so failures are collected and
    reported rather than raised.

Nothing sends unless a channel is configured. An unconfigured channel is
reported as skipped, never silently dropped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.integrations import IntegrationConnection, IntegrationProvider
from app.models.security import MembershipStatus, OrganizationMembership, SecurityUser
from app.schemas.integrations import GmailSendRequest
from app.services.integrations import service as integrations_service
from app.services.procedure import diary
from app.services.security.context import ActorContext

WHATSAPP_API_VERSION = "v21.0"


@dataclass
class DeliveryOutcome:
    channel: str
    recipient: str
    sent: bool
    detail: str | None = None


@dataclass
class ReminderRun:
    on_date: date
    message: str
    hearing_count: int
    outcomes: list[DeliveryOutcome] = field(default_factory=list)

    @property
    def sent_count(self) -> int:
        return sum(1 for item in self.outcomes if item.sent)

    def as_dict(self) -> dict:
        return {
            "date": self.on_date,
            "message": self.message,
            "hearing_count": self.hearing_count,
            "sent_count": self.sent_count,
            "outcomes": [
                {
                    "channel": item.channel,
                    "recipient": item.recipient,
                    "sent": item.sent,
                    "detail": item.detail,
                }
                for item in self.outcomes
            ],
        }


def whatsapp_configured() -> bool:
    return bool(
        settings.whatsapp_enabled
        and settings.whatsapp_phone_number_id
        and settings.whatsapp_access_token
        and settings.whatsapp_template_name
    )


def _mask(number: str) -> str:
    """Log and report the last four digits only."""
    digits = "".join(ch for ch in number if ch.isdigit())
    return f"…{digits[-4:]}" if len(digits) >= 4 else "…"


async def send_whatsapp(to: str, body: str) -> DeliveryOutcome:
    """Send one templated WhatsApp message.

    The digest text is passed as the template's body parameter, so the approved
    template must contain exactly one placeholder.
    """
    if not whatsapp_configured():
        return DeliveryOutcome(
            channel="whatsapp",
            recipient=_mask(to),
            sent=False,
            detail="WhatsApp is not configured (needs phone number id, token and an approved template)",
        )

    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": settings.whatsapp_template_name,
            "language": {"code": settings.whatsapp_template_language},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": body}]}
            ],
        },
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        return DeliveryOutcome("whatsapp", _mask(to), False, f"network error: {type(exc).__name__}")

    if response.status_code >= 400:
        detail = response.text[:200]
        try:
            detail = json.loads(response.text)["error"]["message"][:200]
        except Exception:  # noqa: BLE001 - the raw body is a fine fallback
            pass
        return DeliveryOutcome("whatsapp", _mask(to), False, f"HTTP {response.status_code}: {detail}")
    return DeliveryOutcome("whatsapp", _mask(to), True)


async def send_email(
    db: AsyncSession, actor: ActorContext, to: str, subject: str, body: str
) -> DeliveryOutcome:
    connection = await db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == actor.organization_id,
            IntegrationConnection.provider == IntegrationProvider.GOOGLE_WORKSPACE,
        )
    )
    if not connection:
        return DeliveryOutcome(
            channel="email",
            recipient=to,
            sent=False,
            detail="No Google Workspace connection is configured",
        )
    try:
        await integrations_service.send_gmail(
            db,
            actor,
            connection.id,
            GmailSendRequest(to=[to], subject=subject, text_body=body),
        )
    except Exception as exc:  # noqa: BLE001 - one bad recipient must not stop the run
        return DeliveryOutcome("email", to, False, f"{type(exc).__name__}: {str(exc)[:160]}")
    return DeliveryOutcome("email", to, True)


async def recipients(db: AsyncSession, organization_id) -> list[SecurityUser]:
    """Active members of the firm. Everyone with a live membership gets the day's list."""
    rows = await db.scalars(
        select(SecurityUser)
        .join(OrganizationMembership, OrganizationMembership.user_id == SecurityUser.id)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    )
    return list(rows.unique().all())


async def run_daily_reminder(
    db: AsyncSession,
    actor: ActorContext,
    *,
    on_date: date | None = None,
    language: str = "en",
    channels: tuple[str, ...] = ("email",),
    sync_first: bool = True,
    dry_run: bool = False,
) -> ReminderRun:
    """Build the day's digest and deliver it.

    `dry_run` composes and returns the message without sending, which is how
    the interface previews it and how this is tested.
    """
    target = on_date or diary.tomorrow()
    if sync_first:
        await diary.sync_saved_case_dates(db, actor.organization_id)

    digest = await diary.daily_digest(db, actor.organization_id, on_date=target)
    message = diary.render_digest(digest, language=language)
    run = ReminderRun(on_date=target, message=message, hearing_count=digest["hearing_count"])

    if dry_run:
        return run

    people = await recipients(db, actor.organization_id)
    subject = (
        f"कल की पेशी — {diary.format_date(target, 'hi')}"
        if language == "hi"
        else f"Court diary — {diary.format_date(target, 'en')}"
    )

    for person in people:
        if "email" in channels and person.email:
            run.outcomes.append(await send_email(db, actor, person.email, subject, message))
        if "whatsapp" in channels:
            number = (person.phone_e164 or "").strip()
            if not number:
                run.outcomes.append(
                    DeliveryOutcome("whatsapp", person.email, False, "No WhatsApp number on record")
                )
            else:
                run.outcomes.append(await send_whatsapp(number, message))
    return run
