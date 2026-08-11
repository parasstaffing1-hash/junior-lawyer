from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.matter import Matter
from app.models.security import MatterAccessLevel, MatterSecurityProfile
from app.services.security.context import get_current_actor
from app.services.security.permissions import decide_matter_access, visible_matter_ids
from app.schemas.matter import MatterCreate, MatterRead, MatterUpdate


async def list_matters(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> list[MatterRead]:
    document_count = func.count(Document.id).label("document_count")
    stmt = (
        select(Matter, document_count)
        .outerjoin(Document, Document.matter_id == Matter.id)
    )
    actor = get_current_actor()
    if actor is not None:
        visible = await visible_matter_ids(db, actor)
        if not visible:
            return []
        stmt = stmt.where(Matter.id.in_(visible))
    stmt = (stmt
        .group_by(Matter.id)
        .order_by(Matter.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()

    result: list[MatterRead] = []
    for matter, count in rows:
        item = MatterRead.model_validate(matter)
        item.document_count = count
        result.append(item)
    return result


async def get_matter(db: AsyncSession, matter_id: UUID) -> Matter:
    matter = await db.get(Matter, matter_id)
    if matter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_matter_access(db, actor, matter_id, required=MatterAccessLevel.VIEW)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    return matter


async def create_matter(db: AsyncSession, payload: MatterCreate) -> Matter:
    actor = get_current_actor()
    values = payload.model_dump()
    if actor is not None:
        values["organization_id"] = actor.organization_id
        values["created_by_user_id"] = actor.user_id
    matter = Matter(**values)
    db.add(matter)
    await db.flush()
    if actor is not None:
        db.add(MatterSecurityProfile(matter_id=matter.id, created_by_user_id=actor.user_id))
    await db.commit()
    await db.refresh(matter)
    return matter


async def update_matter(db: AsyncSession, matter_id: UUID, payload: MatterUpdate) -> Matter:
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_matter_access(db, actor, matter_id, required=MatterAccessLevel.MANAGE)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    matter = await get_matter(db, matter_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(matter, field, value)
    await db.commit()
    await db.refresh(matter)
    return matter
