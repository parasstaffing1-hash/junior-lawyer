from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.analytics import AnalyticsRiskStatus
from app.schemas.analytics import (
    AnalyticsDashboard,
    AnalyticsPreferenceRead,
    AnalyticsPreferenceUpdate,
    ClientHealthRead,
    FinancialSummary,
    GoalCreate,
    GoalWithProgress,
    MatterHealthRead,
    MetricDefinitionRead,
    QualitySummary,
    RiskSignalRead,
    RiskSignalUpdate,
    SnapshotCreate,
    SnapshotRead,
    TeamPerformanceRead,
)
from app.services.analytics import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/analytics", tags=["law-firm-analytics"])


@router.get("/dashboard", response_model=AnalyticsDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return AnalyticsDashboard(**await service.dashboard(db, actor))


@router.get("/matter-health", response_model=list[MatterHealthRead])
async def matter_health(include_closed: bool = False, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [MatterHealthRead(**item) for item in await service.matter_health(db, actor, include_closed=include_closed)]


@router.get("/team", response_model=list[TeamPerformanceRead])
async def team(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [TeamPerformanceRead(**item) for item in await service.team_performance(db, actor)]


@router.get("/clients", response_model=list[ClientHealthRead])
async def clients(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ClientHealthRead(**item) for item in await service.client_health(db, actor)]


@router.get("/finance", response_model=FinancialSummary)
async def finance(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return FinancialSummary(**await service.financial_summary(db, actor))


@router.get("/quality", response_model=QualitySummary)
async def quality(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return QualitySummary(**await service.quality_summary(db, actor))


@router.post("/metrics/seed")
async def seed_metrics(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return {"created": await service.seed_metric_definitions(db, actor)}


@router.get("/metrics", response_model=list[MetricDefinitionRead])
async def metrics(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [MetricDefinitionRead.model_validate(row) for row in await service.list_metric_definitions(db, actor)]


@router.get("/preferences", response_model=AnalyticsPreferenceRead)
async def preferences(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return AnalyticsPreferenceRead.model_validate(await service.get_preferences(db, actor))


@router.patch("/preferences", response_model=AnalyticsPreferenceRead)
async def patch_preferences(payload: AnalyticsPreferenceUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return AnalyticsPreferenceRead.model_validate(await service.update_preferences(db, actor, payload.model_dump(exclude_unset=True)))


@router.post("/snapshots", response_model=SnapshotRead, status_code=201)
async def create_snapshot(payload: SnapshotCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SnapshotRead.model_validate(await service.create_snapshot(db, actor, kind=payload.kind, notes=payload.notes))


@router.get("/snapshots", response_model=list[SnapshotRead])
async def snapshots(limit: int = Query(50, ge=1, le=250), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [SnapshotRead.model_validate(row) for row in await service.list_snapshots(db, actor, limit)]


@router.post("/risks/rebuild")
async def rebuild_risks(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.rebuild_risk_signals(db, actor)


@router.get("/risks", response_model=list[RiskSignalRead])
async def risks(status: AnalyticsRiskStatus | None = None, limit: int = Query(200, ge=1, le=1000), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [RiskSignalRead.model_validate(row) for row in await service.list_risk_signals(db, actor, status=status, limit=limit)]


@router.patch("/risks/{signal_id}", response_model=RiskSignalRead)
async def patch_risk(signal_id: UUID, payload: RiskSignalUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return RiskSignalRead.model_validate(await service.update_risk_signal(db, actor, signal_id, payload.status))


@router.post("/goals", response_model=GoalWithProgress, status_code=201)
async def create_goal(payload: GoalCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    goal = await service.create_goal(db, actor, payload.model_dump())
    rows = await service.list_goals(db, actor)
    current = next(item for item in rows if item["goal"].id == goal.id)
    return GoalWithProgress(goal=current["goal"], progress=current["progress"])


@router.get("/goals", response_model=list[GoalWithProgress])
async def goals(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    rows = await service.list_goals(db, actor)
    return [GoalWithProgress(goal=item["goal"], progress=item["progress"]) for item in rows]
