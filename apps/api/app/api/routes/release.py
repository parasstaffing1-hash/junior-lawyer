from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.release import (
    DeploymentApprovalCreate,
    DeploymentApprovalRead,
    PerformanceResultCreate,
    PerformanceRunRead,
    PerformanceScenarioRead,
    ReleaseArtifactCreate,
    ReleaseArtifactRead,
    ReleaseDashboard,
    ReleasePipelineRead,
    ReleaseRunCreate,
    ReleaseRunDetail,
    ReleaseRunRead,
    ReleaseStageRead,
    RollbackPointCreate,
    RollbackPointRead,
    SecurityCaseRead,
    SecurityResultCreate,
    SecurityRunRead,
    StageResultCreate,
)
from app.services.release import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/release", tags=["release-engineering"])


@router.get("/dashboard", response_model=ReleaseDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.dashboard(db, actor)
    return ReleaseDashboard(
        pipeline=ReleasePipelineRead.model_validate(raw["pipeline"]),
        latest_runs=[ReleaseRunRead.model_validate(row) for row in raw["latest_runs"]],
        performance_scenarios=[PerformanceScenarioRead.model_validate(row) for row in raw["performance_scenarios"]],
        security_cases=[SecurityCaseRead.model_validate(row) for row in raw["security_cases"]],
        summary=raw["summary"],
    )


@router.post("/seed", response_model=ReleasePipelineRead)
async def seed(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ReleasePipelineRead.model_validate(await service.get_or_create_pipeline(db, actor))


@router.post("/runs", response_model=ReleaseRunRead, status_code=201)
async def create_run(payload: ReleaseRunCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ReleaseRunRead.model_validate(await service.create_release_run(db, actor, **payload.model_dump()))


@router.get("/runs", response_model=list[ReleaseRunRead])
async def runs(limit: int = Query(30, ge=1, le=200), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ReleaseRunRead.model_validate(row) for row in await service.list_runs(db, actor, limit=limit)]


@router.get("/runs/{run_id}", response_model=ReleaseRunDetail)
async def run_detail(run_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.release_detail(db, actor, run_id)
    return ReleaseRunDetail(
        run=ReleaseRunRead.model_validate(raw["run"]),
        stages=[ReleaseStageRead.model_validate(row) for row in raw["stages"]],
        performance=[PerformanceRunRead.model_validate(row) for row in raw["performance"]],
        security=[SecurityRunRead.model_validate(row) for row in raw["security"]],
        artifacts=[row for row in raw["artifacts"]],
        rollback_points=[RollbackPointRead.model_validate(row) for row in raw["rollback_points"]],
        approvals=[DeploymentApprovalRead.model_validate(row) for row in raw["approvals"]],
        gate=raw["gate"],
    )


@router.post("/runs/{run_id}/stages/{stage_key}", response_model=ReleaseStageRead)
async def stage_result(run_id: UUID, stage_key: str, payload: StageResultCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ReleaseStageRead.model_validate(await service.record_stage_result(db, actor, run_id, stage_key, **payload.model_dump()))


@router.post("/runs/{run_id}/performance", response_model=PerformanceRunRead, status_code=201)
async def performance_result(run_id: UUID, payload: PerformanceResultCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return PerformanceRunRead.model_validate(await service.submit_performance_result(db, actor, run_id, **payload.model_dump()))


@router.post("/runs/{run_id}/security", response_model=SecurityRunRead, status_code=201)
async def security_result(run_id: UUID, payload: SecurityResultCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SecurityRunRead.model_validate(await service.submit_security_result(db, actor, run_id, **payload.model_dump()))


@router.post("/runs/{run_id}/artifacts", response_model=ReleaseArtifactRead, status_code=201)
async def register_artifact(run_id: UUID, payload: ReleaseArtifactCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ReleaseArtifactRead.model_validate(await service.register_artifact(db, actor, run_id, **payload.model_dump()))


@router.post("/runs/{run_id}/rollback-points", response_model=RollbackPointRead, status_code=201)
async def rollback_point(run_id: UUID, payload: RollbackPointCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return RollbackPointRead.model_validate(await service.create_rollback_point(db, actor, run_id, **payload.model_dump()))


@router.post("/runs/{run_id}/evaluate")
async def evaluate(run_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.evaluate_release(db, actor, run_id)


@router.post("/runs/{run_id}/approval", response_model=DeploymentApprovalRead)
async def approve(run_id: UUID, payload: DeploymentApprovalCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return DeploymentApprovalRead.model_validate(await service.approve_release(db, actor, run_id, **payload.model_dump()))
