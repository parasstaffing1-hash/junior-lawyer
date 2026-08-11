from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.ai import (
    AIPrepareResponse,
    AIProviderStatusRead,
    AIReasoningRequest,
    AIReviewRequest,
    AIRunRead,
)
from app.services.ai import service

router = APIRouter(prefix="/ai", tags=["verified-ai"])


@router.get("/providers", response_model=AIProviderStatusRead)
async def providers() -> AIProviderStatusRead:
    return AIProviderStatusRead.model_validate(await service.provider_status())


@router.post("/prepare", response_model=AIPrepareResponse)
async def prepare(
    payload: AIReasoningRequest,
    db: AsyncSession = Depends(get_db),
) -> AIPrepareResponse:
    return AIPrepareResponse.model_validate(await service.prepare_reasoning(db, payload))


@router.post("/runs", response_model=AIRunRead, status_code=status.HTTP_201_CREATED)
async def run(
    payload: AIReasoningRequest,
    db: AsyncSession = Depends(get_db),
) -> AIRunRead:
    return AIRunRead.model_validate(await service.run_reasoning(db, payload))


@router.get("/runs", response_model=list[AIRunRead])
async def runs(
    matter_id: UUID | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[AIRunRead]:
    return [AIRunRead.model_validate(row) for row in await service.list_runs(db, matter_id=matter_id, limit=limit)]


@router.get("/runs/{run_id}", response_model=AIRunRead)
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db)) -> AIRunRead:
    return AIRunRead.model_validate(await service.get_run(db, run_id))


@router.patch("/runs/{run_id}/review", response_model=AIRunRead)
async def review_run(
    run_id: UUID,
    payload: AIReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> AIRunRead:
    return AIRunRead.model_validate(await service.review_run(db, run_id, payload))
