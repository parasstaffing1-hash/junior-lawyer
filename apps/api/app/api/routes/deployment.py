from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.deployment import (
    DeploymentChangeWindowCreate, DeploymentChangeWindowRead, DeploymentDashboard,
    DeploymentEnvironmentCreate, DeploymentEnvironmentRead, DeploymentRolloutCreate,
    DeploymentRolloutDetail, DeploymentRolloutRead, DeploymentSecretReferenceCreate,
    DeploymentSecretReferenceRead, DeploymentStepUpdate, DeploymentRolloutStepRead,
    RuntimeReadiness,
)
from app.services.deployment import service
from app.services.deployment.readiness import evaluate_runtime_readiness
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor
from app.core.config import settings

router = APIRouter(prefix="/deployment", tags=["deployment"])

@router.get("/readiness", response_model=RuntimeReadiness)
async def readiness(actor: ActorContext = Depends(require_actor)):
    return evaluate_runtime_readiness(settings)

@router.get("/dashboard", response_model=DeploymentDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.dashboard(db, actor)

@router.post("/environments", response_model=DeploymentEnvironmentRead, status_code=201)
async def create_environment(payload: DeploymentEnvironmentCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_environment(db, actor, **payload.model_dump())

@router.post("/change-windows", response_model=DeploymentChangeWindowRead, status_code=201)
async def create_change_window(payload: DeploymentChangeWindowCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_change_window(db, actor, **payload.model_dump())

@router.post("/secret-references", response_model=DeploymentSecretReferenceRead, status_code=201)
async def secret_reference(payload: DeploymentSecretReferenceCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.register_secret_reference(db, actor, **payload.model_dump())

@router.post("/rollouts", response_model=DeploymentRolloutRead, status_code=201)
async def create_rollout(payload: DeploymentRolloutCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_rollout(db, actor, **payload.model_dump())

@router.get("/rollouts/{rollout_id}", response_model=DeploymentRolloutDetail)
async def get_rollout(rollout_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.rollout_detail(db, actor, rollout_id)

@router.patch("/rollouts/{rollout_id}/steps/{step_id}", response_model=DeploymentRolloutStepRead)
async def update_step(rollout_id: UUID, step_id: UUID, payload: DeploymentStepUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.update_step(db, actor, rollout_id, step_id, **payload.model_dump())
