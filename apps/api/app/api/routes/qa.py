from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.qa import (
    EvaluationCaseCreate,
    EvaluationCaseRead,
    EvaluationRunCreate,
    EvaluationRunDetail,
    EvaluationRunRead,
    EvaluationSuiteDetail,
    EvaluationSuiteRead,
    QADashboard,
    ReleaseGateRead,
    ReleaseGateUpdate,
)
from app.services.qa import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/qa", tags=["quality-assurance"])


@router.get("/dashboard", response_model=QADashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.dashboard(db, actor)
    return QADashboard(
        suites=[EvaluationSuiteRead.model_validate(row) for row in raw["suites"]],
        latest_runs=[EvaluationRunRead.model_validate(row) for row in raw["latest_runs"]],
        default_gate=ReleaseGateRead.model_validate(raw["default_gate"]) if raw["default_gate"] else None,
        latest_gate_result=raw["latest_gate_result"],
        summary=raw["summary"],
    )


@router.post("/seed", response_model=EvaluationSuiteRead)
async def seed(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return EvaluationSuiteRead.model_validate(await service.seed_default_suite(db, actor))


@router.get("/suites", response_model=list[EvaluationSuiteRead])
async def suites(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [EvaluationSuiteRead.model_validate(row) for row in await service.list_suites(db, actor)]


@router.get("/suites/{suite_id}", response_model=EvaluationSuiteDetail)
async def suite(suite_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.suite_detail(db, actor, suite_id)
    return EvaluationSuiteDetail(suite=EvaluationSuiteRead.model_validate(raw["suite"]), cases=[EvaluationCaseRead.model_validate(row) for row in raw["cases"]])


@router.post("/suites/{suite_id}/cases", response_model=EvaluationCaseRead, status_code=201)
async def add_case(suite_id: UUID, payload: EvaluationCaseCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return EvaluationCaseRead.model_validate(await service.add_case(db, actor, suite_id, payload.model_dump()))


@router.post("/suites/{suite_id}/runs", response_model=EvaluationRunRead, status_code=201)
async def run_suite(suite_id: UUID, payload: EvaluationRunCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return EvaluationRunRead.model_validate(await service.run_suite(db, actor, suite_id, build_ref=payload.build_ref))


@router.get("/runs", response_model=list[EvaluationRunRead])
async def runs(limit: int = Query(30, ge=1, le=200), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [EvaluationRunRead.model_validate(row) for row in await service.list_runs(db, actor, limit=limit)]


@router.get("/runs/{run_id}", response_model=EvaluationRunDetail)
async def run_detail(run_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.run_detail(db, actor, run_id)
    return EvaluationRunDetail(
        run=EvaluationRunRead.model_validate(raw["run"]),
        case_runs=[row for row in raw["case_runs"]],
        findings=[row for row in raw["findings"]],
        metrics=[{"category": row.category, "metric_key": row.metric_key, "value": row.value, "threshold": row.threshold, "passed": row.passed, "details_json": row.details_json} for row in raw["metrics"]],
        gate=raw["gate"],
    )


@router.get("/release-gate", response_model=ReleaseGateRead)
async def gate(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ReleaseGateRead.model_validate(await service.get_or_create_gate(db, actor))


@router.patch("/release-gate", response_model=ReleaseGateRead)
async def patch_gate(payload: ReleaseGateUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ReleaseGateRead.model_validate(await service.update_gate(db, actor, payload.model_dump(exclude_unset=True)))
