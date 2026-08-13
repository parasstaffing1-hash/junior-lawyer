"""The daily diary: what is listed tomorrow, and telling the lawyer about it.

A district practice loses money to one thing above all others — a missed date.
Not weak drafting, not thin research: a peshi nobody entered in the diary, a
dismissal for default, and a restoration application done for free out of
shame.

Three pieces, deliberately separated:

  * `sync_saved_case_dates` moves next-hearing dates from saved cases into the
    hearings table, so the diary fills itself instead of being typed;
  * `daily_digest` assembles a day's listings grouped by court, because a
    lawyer plans by building, not by matter;
  * `render_digest` writes the message, in the lawyer's own language.

Delivery lives in `reminders.py`. Composition is kept apart from sending so the
message can be previewed, tested and read back without anything leaving the
building.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_lookup import SavedCase
from app.models.matter import Matter
from app.models.procedure import Hearing, HearingStatus, MatterDeadline

# Hearings created from a court record are tagged, so a later refresh updates
# the same row instead of creating a duplicate, and so a lawyer can see which
# dates were captured rather than entered.
DIARY_SOURCE = "case_lookup_sync"

HINDI_MONTHS = {
    1: "जनवरी", 2: "फ़रवरी", 3: "मार्च", 4: "अप्रैल", 5: "मई", 6: "जून",
    7: "जुलाई", 8: "अगस्त", 9: "सितंबर", 10: "अक्टूबर", 11: "नवंबर", 12: "दिसंबर",
}


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def format_date(value: date, language: str) -> str:
    if language == "hi":
        return f"{value.day} {HINDI_MONTHS[value.month]} {value.year}"
    return value.strftime("%d %b %Y")


async def sync_saved_case_dates(
    db: AsyncSession, organization_id: UUID, *, commit: bool = True
) -> dict:
    """Copy next-hearing dates from saved cases into the diary.

    Only saved cases linked to a matter are synced — an unlinked case is
    research, not a listing. Idempotent: re-running updates the existing row.

    The ceiling here is the court source, not this function. Where a saved case
    was never refreshed against the official record, its next date is only as
    current as the last import, and `stale` counts those so the caller can say
    so rather than imply a freshness that was never checked.
    """
    rows = list(
        (
            await db.scalars(
                select(SavedCase).where(
                    SavedCase.organization_id == organization_id,
                    SavedCase.matter_id.is_not(None),
                    SavedCase.next_hearing_date.is_not(None),
                )
            )
        ).all()
    )

    created = updated = skipped = stale = 0
    today = date.today()
    now = datetime.now(timezone.utc)

    for saved in rows:
        if saved.next_hearing_date < today:
            skipped += 1
            continue
        if saved.stale_after and _as_utc(saved.stale_after) < now:
            stale += 1

        scheduled = datetime.combine(saved.next_hearing_date, time(10, 30), tzinfo=timezone.utc)
        existing = await db.scalar(
            select(Hearing).where(
                Hearing.matter_id == saved.matter_id,
                Hearing.scheduled_for == scheduled,
            )
        )
        if existing:
            # Never overwrite a hearing a lawyer entered or edited by hand.
            if (existing.metadata_json or {}).get("source") != DIARY_SOURCE:
                skipped += 1
                continue
            existing.court_name = saved.court_name or existing.court_name
            existing.judge_or_bench = saved.judge or saved.bench or existing.judge_or_bench
            existing.purpose = saved.case_stage or existing.purpose
            existing.metadata_json = {
                **(existing.metadata_json or {}),
                "source": DIARY_SOURCE,
                "saved_case_id": str(saved.id),
                "synced_at": now.isoformat(),
            }
            updated += 1
            continue

        db.add(
            Hearing(
                matter_id=saved.matter_id,
                scheduled_for=scheduled,
                court_name=saved.court_name,
                judge_or_bench=saved.judge or saved.bench,
                purpose=saved.case_stage or "Hearing",
                status=HearingStatus.SCHEDULED,
                source_url=saved.source_url,
                metadata_json={
                    "source": DIARY_SOURCE,
                    "saved_case_id": str(saved.id),
                    "case_number": saved.case_number,
                    "cnr": saved.cnr,
                    "synced_at": now.isoformat(),
                    # Recorded so the interface can mark a date whose source has
                    # not been re-checked since it went stale.
                    "source_stale": bool(saved.stale_after and _as_utc(saved.stale_after) < now),
                },
            )
        )
        created += 1

    if commit:
        await db.commit()
    return {
        "saved_cases_considered": len(rows),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "stale_sources": stale,
    }


async def daily_digest(
    db: AsyncSession, organization_id: UUID, *, on_date: date | None = None
) -> dict:
    """Everything listed on one day, grouped by court."""
    target = on_date or date.today()
    start = datetime.combine(target, time.min, tzinfo=timezone.utc)
    end = datetime.combine(target, time.max, tzinfo=timezone.utc)

    matter_ids = set(
        (
            await db.scalars(
                select(Matter.id).where(Matter.organization_id == organization_id)
            )
        ).all()
    )

    hearings = [
        row
        for row in (
            await db.scalars(
                select(Hearing)
                .where(Hearing.scheduled_for >= start, Hearing.scheduled_for <= end)
                .order_by(Hearing.scheduled_for)
            )
        ).all()
        if row.matter_id in matter_ids
        and row.status in {HearingStatus.SCHEDULED, HearingStatus.ADJOURNED}
    ]

    deadlines = [
        row
        for row in (
            await db.scalars(
                select(MatterDeadline)
                .where(MatterDeadline.due_date == target)
                .order_by(MatterDeadline.due_date)
            )
        ).all()
        if row.matter_id in matter_ids and row.completed_at is None
    ]

    titles = {
        row.id: row.title
        for row in (
            await db.scalars(select(Matter).where(Matter.id.in_(matter_ids or {None})))
        ).all()
    } if matter_ids else {}

    by_court: dict[str, list[dict]] = defaultdict(list)
    for hearing in hearings:
        court = (hearing.court_name or "Court not recorded").strip()
        by_court[court].append(
            {
                "hearing_id": str(hearing.id),
                "matter_id": str(hearing.matter_id),
                "matter_title": titles.get(hearing.matter_id, "Matter"),
                "time": _as_utc(hearing.scheduled_for).strftime("%H:%M"),
                "courtroom": hearing.courtroom,
                "purpose": hearing.purpose,
                "case_number": (hearing.metadata_json or {}).get("case_number"),
                "auto_captured": (hearing.metadata_json or {}).get("source") == DIARY_SOURCE,
                "source_stale": bool((hearing.metadata_json or {}).get("source_stale")),
            }
        )

    return {
        "date": target,
        "hearing_count": len(hearings),
        "deadline_count": len(deadlines),
        "courts": [
            {"court_name": court, "items": items} for court, items in sorted(by_court.items())
        ],
        "deadlines": [
            {
                "deadline_id": str(row.id),
                "matter_id": str(row.matter_id),
                "matter_title": titles.get(row.matter_id, "Matter"),
                "title": row.title,
                "requires_review": not row.reviewed_by_lawyer,
            }
            for row in deadlines
        ],
    }


def render_digest(digest: dict, *, language: str = "en") -> str:
    """The message a lawyer actually reads, on a phone, in a corridor.

    Court and count first, because that is what decides the morning. Detail
    after, because it is read only if the count is surprising.
    """
    when = digest["date"]
    hearings = digest["hearing_count"]
    deadlines = digest["deadline_count"]

    if language == "hi":
        if not hearings and not deadlines:
            return f"{format_date(when, 'hi')}: कोई पेशी या समय-सीमा नहीं।"
        head = f"{format_date(when, 'hi')} — {hearings} पेशी"
        if deadlines:
            head += f", {deadlines} समय-सीमा"
        lines = [head, ""]
        for court in digest["courts"]:
            lines.append(f"{court['court_name']}: {len(court['items'])}")
            for item in court["items"]:
                room = f" ({item['courtroom']})" if item.get("courtroom") else ""
                marker = " ⚠" if item.get("source_stale") else ""
                lines.append(f"  {item['time']}{room} — {item['matter_title']}{marker}")
        if digest["deadlines"]:
            lines.append("")
            lines.append("समय-सीमा:")
            for item in digest["deadlines"]:
                lines.append(f"  {item['title']} — {item['matter_title']}")
        return "\n".join(lines)

    if not hearings and not deadlines:
        return f"{format_date(when, 'en')}: no hearings or deadlines."
    head = f"{format_date(when, 'en')} — {hearings} hearing{'s' if hearings != 1 else ''}"
    if deadlines:
        head += f", {deadlines} deadline{'s' if deadlines != 1 else ''}"
    lines = [head, ""]
    for court in digest["courts"]:
        lines.append(f"{court['court_name']}: {len(court['items'])}")
        for item in court["items"]:
            room = f" ({item['courtroom']})" if item.get("courtroom") else ""
            marker = " (source not re-checked)" if item.get("source_stale") else ""
            lines.append(f"  {item['time']}{room} — {item['matter_title']}{marker}")
    if digest["deadlines"]:
        lines.append("")
        lines.append("Deadlines:")
        for item in digest["deadlines"]:
            lines.append(f"  {item['title']} — {item['matter_title']}")
    return "\n".join(lines)


def tomorrow() -> date:
    return date.today() + timedelta(days=1)
