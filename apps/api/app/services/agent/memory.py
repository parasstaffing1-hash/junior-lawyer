"""Case memory: one standing record of what is known about a matter.

The facts, timeline, contradictions and evidence matrix already persist in the
intelligence tables. What had nowhere to live was the lawyer's reading of them
— which issues are in play, what is still unanswered, and the strategy. Those
three are stored here and are never overwritten by a refresh.

Everything else in memory is derived. `refresh` recomputes the snapshot from
the existing services so an agent step can be handed one object rather than
issuing six queries and hoping they agree.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import MatterMemory
from app.services import matters as matters_service
from app.services.intelligence import service as intelligence_service
from app.services.procedure import service as procedure_service


async def _row(db: AsyncSession, matter_id: UUID) -> MatterMemory | None:
    result = await db.execute(select(MatterMemory).where(MatterMemory.matter_id == matter_id))
    return result.scalar_one_or_none()


async def get_or_create(db: AsyncSession, matter_id: UUID) -> MatterMemory:
    """Memory exists for every matter that is asked about, so callers never
    branch on its absence."""
    row = await _row(db, matter_id)
    if row is not None:
        return row
    # Confirms the matter exists (and raises the service's own 404 if not)
    # before writing a row that would dangle.
    await matters_service.get_matter(db, matter_id)
    row = MatterMemory(matter_id=matter_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def build_snapshot(db: AsyncSession, matter_id: UUID) -> dict:
    """Counts and headline items from the tables that already hold the detail.

    Deliberately shallow: memory records how much of each kind exists and the
    few items a summary would lead with, not a second copy of the record.
    """
    facts = await intelligence_service.list_facts(db, matter_id)
    timeline = await intelligence_service.list_timeline(db, matter_id)
    contradictions = await intelligence_service.list_contradictions(db, matter_id)
    review_items = await intelligence_service.list_review_items(db, matter_id)
    deadlines = await procedure_service.list_deadlines(db, matter_id=matter_id)

    unresolved = [c for c in contradictions if str(c.status) != "resolved"]
    return {
        "fact_count": len(facts),
        "timeline_count": len(timeline),
        "contradiction_count": len(contradictions),
        "unresolved_contradiction_count": len(unresolved),
        "review_item_count": len(review_items),
        "deadline_count": len(deadlines),
        "first_event": timeline[0].event_date.isoformat() if timeline else None,
        "last_event": timeline[-1].event_date.isoformat() if timeline else None,
        "top_contradictions": [
            {"label": c.label, "severity": str(c.severity)} for c in unresolved[:5]
        ],
    }


async def refresh(db: AsyncSession, matter_id: UUID) -> MatterMemory:
    """Recompute the derived half. The lawyer-owned fields are left alone."""
    row = await get_or_create(db, matter_id)
    row.snapshot_json = await build_snapshot(db, matter_id)
    row.refreshed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row


async def update(
    db: AsyncSession,
    matter_id: UUID,
    *,
    issues: list | None = None,
    open_questions: list | None = None,
    strategy_notes: str | None = None,
) -> MatterMemory:
    """Set the lawyer-owned fields. Omitted arguments are left unchanged, so a
    caller editing only the strategy cannot blank the issues."""
    row = await get_or_create(db, matter_id)
    if issues is not None:
        row.issues_json = issues
    if open_questions is not None:
        row.open_questions_json = open_questions
    if strategy_notes is not None:
        row.strategy_notes = strategy_notes
    await db.commit()
    await db.refresh(row)
    return row
