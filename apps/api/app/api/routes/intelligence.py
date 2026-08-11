from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.intelligence import (
    ContradictionStatus,
    FactStatus,
    ReviewStatus,
    StatementKind,
)
from app.schemas.intelligence import (
    ContradictionRead,
    ContradictionUpdate,
    EvidenceMatrixRead,
    FactRead,
    FactUpdate,
    IntelligenceSummaryRead,
    RebuildResultRead,
    ReviewItemRead,
    ReviewItemUpdate,
    StatementRead,
    TimelineEventRead,
)
from app.services.intelligence import service

router = APIRouter(tags=["matter-intelligence"])


@router.post(
    "/matters/{matter_id}/intelligence/rebuild",
    response_model=RebuildResultRead,
)
async def rebuild_intelligence(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RebuildResultRead:
    return await service.rebuild_matter_intelligence(db, matter_id)


@router.get(
    "/matters/{matter_id}/intelligence/summary",
    response_model=IntelligenceSummaryRead,
)
async def intelligence_summary(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> IntelligenceSummaryRead:
    return await service.get_intelligence_summary(db, matter_id)


@router.get("/matters/{matter_id}/facts", response_model=list[FactRead])
async def list_facts(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[FactRead]:
    return await service.list_facts(db, matter_id)


@router.patch("/facts/{fact_id}", response_model=FactRead)
async def update_fact(
    fact_id: UUID,
    payload: FactUpdate,
    db: AsyncSession = Depends(get_db),
) -> FactRead:
    return await service.update_fact_status(db, fact_id, payload.status)


@router.get("/matters/{matter_id}/timeline", response_model=list[TimelineEventRead])
async def list_timeline(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[TimelineEventRead]:
    return await service.list_timeline(db, matter_id)


@router.get("/matters/{matter_id}/statements", response_model=list[StatementRead])
async def list_statements(
    matter_id: UUID,
    kind: StatementKind | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[StatementRead]:
    return await service.list_statements(db, matter_id, kind=kind)


@router.get(
    "/matters/{matter_id}/contradictions",
    response_model=list[ContradictionRead],
)
async def list_contradictions(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ContradictionRead]:
    return await service.list_contradictions(db, matter_id)


@router.patch("/contradictions/{contradiction_id}", response_model=ContradictionRead)
async def update_contradiction(
    contradiction_id: UUID,
    payload: ContradictionUpdate,
    db: AsyncSession = Depends(get_db),
) -> ContradictionRead:
    return await service.update_contradiction_status(db, contradiction_id, payload.status)


@router.get("/matters/{matter_id}/evidence", response_model=EvidenceMatrixRead)
async def evidence_matrix(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EvidenceMatrixRead:
    return await service.get_evidence_matrix(db, matter_id)


@router.get("/matters/{matter_id}/review", response_model=list[ReviewItemRead])
async def list_review_items(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ReviewItemRead]:
    return await service.list_review_items(db, matter_id)


@router.patch("/review/{review_id}", response_model=ReviewItemRead)
async def update_review_item(
    review_id: UUID,
    payload: ReviewItemUpdate,
    db: AsyncSession = Depends(get_db),
) -> ReviewItemRead:
    return await service.update_review_status(db, review_id, payload.status)
