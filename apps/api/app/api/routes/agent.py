from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.agent import (
    AgentRecipeRead,
    AgentRunCreate,
    AgentRunDetail,
    AgentRunRead,
    AgentRunReview,
    MatterMemoryRead,
    MatterMemoryUpdate,
)
from app.services.agent import memory as memory_service
from app.services.agent import service

router = APIRouter(prefix="/agent", tags=["agent-and-case-memory"])


@router.get("/recipes", response_model=list[AgentRecipeRead])
async def list_recipes():
    return service.list_recipes()


@router.get("/matters/{matter_id}/memory", response_model=MatterMemoryRead)
async def get_memory(matter_id: UUID, db: AsyncSession = Depends(get_db)):
    return await memory_service.get_or_create(db, matter_id)


@router.post("/matters/{matter_id}/memory/refresh", response_model=MatterMemoryRead)
async def refresh_memory(matter_id: UUID, db: AsyncSession = Depends(get_db)):
    """Recomputes the derived snapshot. The lawyer-owned fields are untouched."""
    return await memory_service.refresh(db, matter_id)


@router.patch("/matters/{matter_id}/memory", response_model=MatterMemoryRead)
async def update_memory(
    matter_id: UUID, payload: MatterMemoryUpdate, db: AsyncSession = Depends(get_db)
):
    return await memory_service.update(
        db,
        matter_id,
        issues=payload.issues,
        open_questions=payload.open_questions,
        strategy_notes=payload.strategy_notes,
    )


@router.post("/runs", response_model=AgentRunDetail, status_code=status.HTTP_201_CREATED)
async def start_run(payload: AgentRunCreate, db: AsyncSession = Depends(get_db)):
    """Runs the recipe and returns it awaiting approval. Nothing is acted on."""
    return await service.start_run(
        db, payload.matter_id, payload.recipe, output_language=payload.output_language
    )


@router.get("/runs", response_model=list[AgentRunRead])
async def list_runs(
    matter_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_runs(db, matter_id=matter_id, limit=limit)


@router.get("/runs/{run_id}", response_model=AgentRunDetail)
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_run(db, run_id)


@router.patch("/runs/{run_id}/review", response_model=AgentRunDetail)
async def review_run(
    run_id: UUID, payload: AgentRunReview, db: AsyncSession = Depends(get_db)
):
    return await service.review_run(
        db, run_id, approved=payload.approved, notes=payload.notes, reviewer=payload.reviewer
    )
