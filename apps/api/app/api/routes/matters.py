from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.matter import (
    MatterCreate,
    MatterPartyCreate,
    MatterPartyRead,
    MatterPartyUpdate,
    MatterRead,
    MatterUpdate,
    PartyConflictReport,
)
from app.services import matters as matter_service
from app.services import parties as party_service

router = APIRouter(prefix="/matters", tags=["matters"])


@router.get("", response_model=list[MatterRead])
async def list_matters(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[MatterRead]:
    return await matter_service.list_matters(db, limit=limit, offset=offset)


@router.post("", response_model=MatterRead, status_code=status.HTTP_201_CREATED)
async def create_matter(
    payload: MatterCreate,
    db: AsyncSession = Depends(get_db),
) -> MatterRead:
    matter = await matter_service.create_matter(db, payload)
    return MatterRead.model_validate(matter)


@router.get("/{matter_id}", response_model=MatterRead)
async def get_matter(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MatterRead:
    matter = await matter_service.get_matter(db, matter_id)
    response = MatterRead.model_validate(matter)
    response.document_count = len(matter.documents)
    return response


@router.patch("/{matter_id}", response_model=MatterRead)
async def update_matter(
    matter_id: UUID,
    payload: MatterUpdate,
    db: AsyncSession = Depends(get_db),
) -> MatterRead:
    matter = await matter_service.update_matter(db, matter_id, payload)
    return MatterRead.model_validate(matter)


# --- parties -----------------------------------------------------------------


@router.get("/{matter_id}/parties", response_model=list[MatterPartyRead])
async def list_parties(matter_id: UUID, db: AsyncSession = Depends(get_db)) -> list[MatterPartyRead]:
    rows = await party_service.list_parties(db, matter_id)
    return [MatterPartyRead.model_validate(row) for row in rows]


@router.post(
    "/{matter_id}/parties", response_model=MatterPartyRead, status_code=status.HTTP_201_CREATED
)
async def add_party(
    matter_id: UUID, payload: MatterPartyCreate, db: AsyncSession = Depends(get_db)
) -> MatterPartyRead:
    return MatterPartyRead.model_validate(await party_service.add_party(db, matter_id, payload))


@router.patch("/{matter_id}/parties/{party_id}", response_model=MatterPartyRead)
async def update_party(
    matter_id: UUID,
    party_id: UUID,
    payload: MatterPartyUpdate,
    db: AsyncSession = Depends(get_db),
) -> MatterPartyRead:
    return MatterPartyRead.model_validate(
        await party_service.update_party(db, matter_id, party_id, payload)
    )


@router.delete("/{matter_id}/parties/{party_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_party(
    matter_id: UUID, party_id: UUID, db: AsyncSession = Depends(get_db)
) -> None:
    await party_service.remove_party(db, matter_id, party_id)


@router.get("/parties/screen", response_model=PartyConflictReport)
async def screen_party(
    name: str = Query(min_length=2, max_length=300), db: AsyncSession = Depends(get_db)
) -> PartyConflictReport:
    """Check a name against parties already recorded on visible matters."""
    return await party_service.screen_name(db, name)
