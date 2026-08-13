"""Parties on a matter, including the other side.

Opposing parties were previously only loose JSON on a conflict-check record,
which meant they could not be searched, corrected, or screened against later
intake. They are rows now, and the screen runs off the normalized name.
"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.matter import Matter, MatterParty, PartyRole
from app.models.security import MatterAccessLevel
from app.schemas.matter import (
    MatterPartyCreate,
    MatterPartyUpdate,
    PartyConflictHit,
    PartyConflictReport,
)
from app.services.security.context import get_current_actor
from app.services.security.permissions import decide_matter_access, visible_matter_ids

# Honorifics and entity suffixes that carry no identifying weight. Dropping
# them lets "M/s ABC Pvt. Ltd." screen against "ABC Limited".
_NOISE = {
    "m/s", "mr", "mrs", "ms", "shri", "smt", "dr", "the",
    "pvt", "private", "ltd", "limited", "llp", "inc", "co", "company", "corp",
}


def normalize_name(value: str) -> str:
    """Case-fold, strip punctuation and drop entity noise words."""
    lowered = re.sub(r"[^\w\s/]", " ", (value or "").lower())
    words = [w for w in lowered.split() if w and w not in _NOISE]
    return " ".join(words)


async def _guard(db: AsyncSession, matter_id: UUID, required: MatterAccessLevel) -> Matter:
    matter = await db.get(Matter, matter_id)
    if matter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_matter_access(db, actor, matter_id, required=required)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    return matter


async def list_parties(db: AsyncSession, matter_id: UUID) -> list[MatterParty]:
    await _guard(db, matter_id, MatterAccessLevel.VIEW)
    return list(
        (
            await db.scalars(
                select(MatterParty)
                .where(MatterParty.matter_id == matter_id)
                .order_by(MatterParty.role, MatterParty.name)
            )
        ).all()
    )


async def add_party(
    db: AsyncSession, matter_id: UUID, payload: MatterPartyCreate
) -> MatterParty:
    await _guard(db, matter_id, MatterAccessLevel.WORK)
    row = MatterParty(
        matter_id=matter_id,
        normalized_name=normalize_name(payload.name),
        **payload.model_dump(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_party(
    db: AsyncSession, matter_id: UUID, party_id: UUID, payload: MatterPartyUpdate
) -> MatterParty:
    await _guard(db, matter_id, MatterAccessLevel.WORK)
    row = await db.get(MatterParty, party_id)
    if row is None or row.matter_id != matter_id:
        raise HTTPException(status_code=404, detail="Party not found")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(row, field, value)
    if "name" in changes and changes["name"]:
        row.normalized_name = normalize_name(changes["name"])
    await db.commit()
    await db.refresh(row)
    return row


async def remove_party(db: AsyncSession, matter_id: UUID, party_id: UUID) -> None:
    await _guard(db, matter_id, MatterAccessLevel.WORK)
    row = await db.get(MatterParty, party_id)
    if row is None or row.matter_id != matter_id:
        raise HTTPException(status_code=404, detail="Party not found")
    await db.delete(row)
    await db.commit()


async def screen_name(db: AsyncSession, name: str) -> PartyConflictReport:
    """Find every matter where this name already appears as a party.

    Only matters the actor can see are searched — a conflict screen must not
    become a way to enumerate matters someone has no access to. That is a real
    limitation, not an oversight: a firm-wide screen belongs to the CRM
    conflict-check flow, which runs with organization scope.
    """
    normalized = normalize_name(name)
    if not normalized:
        return PartyConflictReport(query=name, normalized_query="", hits=[])

    stmt = (
        select(MatterParty, Matter.title)
        .join(Matter, Matter.id == MatterParty.matter_id)
        .where(MatterParty.normalized_name == normalized)
        .order_by(Matter.title)
    )
    actor = get_current_actor()
    if actor is not None:
        visible = await visible_matter_ids(db, actor)
        if not visible:
            return PartyConflictReport(query=name, normalized_query=normalized, hits=[])
        stmt = stmt.where(MatterParty.matter_id.in_(visible))

    rows = (await db.execute(stmt)).all()
    hits = [
        PartyConflictHit(
            party_id=party.id,
            matter_id=party.matter_id,
            matter_title=title,
            name=party.name,
            role=party.role,
            is_active=party.is_active,
        )
        for party, title in rows
    ]
    return PartyConflictReport(
        query=name,
        normalized_query=normalized,
        hits=hits,
        opposing_hit=any(hit.role == PartyRole.OPPOSING for hit in hits),
    )
