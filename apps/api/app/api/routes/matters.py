from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.matter import MatterCreate, MatterRead, MatterUpdate
from app.services import matters as matter_service

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
