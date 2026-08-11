from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.validation import (
    PilotReadinessRead,
    PilotReadinessUpdate,
    ReleaseCandidateManifestRead,
    ValidationCampaignCreate,
    ValidationCampaignDetail,
    ValidationCampaignRead,
    ValidationDashboard,
    ValidationDatasetCreate,
    ValidationDatasetRead,
    ValidationEvidenceCreate,
    ValidationEvidenceRead,
    ValidationScenarioRead,
    ValidationScenarioResultCreate,
    ValidationScenarioRunRead,
    ValidationSignoffCreate,
    ValidationSignoffRead,
)
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor
from app.services.validation import service

router = APIRouter(prefix="/validation", tags=["release-candidate-validation"])


@router.get("/dashboard", response_model=ValidationDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.dashboard(db, actor)
    return ValidationDashboard(
        scenarios=[ValidationScenarioRead.model_validate(row) for row in raw["scenarios"]],
        campaigns=[ValidationCampaignRead.model_validate(row) for row in raw["campaigns"]],
        summary=raw["summary"],
    )


@router.post("/seed", response_model=list[ValidationScenarioRead])
async def seed(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ValidationScenarioRead.model_validate(row) for row in await service.seed_scenarios(db, actor)]


@router.post("/campaigns", response_model=ValidationCampaignRead, status_code=201)
async def create_campaign(payload: ValidationCampaignCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ValidationCampaignRead.model_validate(await service.create_campaign(db, actor, **payload.model_dump()))


@router.get("/campaigns", response_model=list[ValidationCampaignRead])
async def campaigns(limit: int = Query(30, ge=1, le=200), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ValidationCampaignRead.model_validate(row) for row in await service.list_campaigns(db, actor, limit)]


@router.get("/campaigns/{campaign_id}", response_model=ValidationCampaignDetail)
async def campaign_detail(campaign_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.detail(db, actor, campaign_id)
    return ValidationCampaignDetail(
        campaign=ValidationCampaignRead.model_validate(raw["campaign"]),
        scenarios=[ValidationScenarioRead.model_validate(row) for row in raw["scenarios"]],
        runs=[ValidationScenarioRunRead.model_validate(row) for row in raw["runs"]],
        checks=[PilotReadinessRead.model_validate(row) for row in raw["checks"]],
        datasets=[ValidationDatasetRead.model_validate(row) for row in raw["datasets"]],
        signoffs=[ValidationSignoffRead.model_validate(row) for row in raw["signoffs"]],
        manifest=ReleaseCandidateManifestRead.model_validate(raw["manifest"]) if raw["manifest"] else None,
        gate=raw["gate"],
    )


@router.post("/campaigns/{campaign_id}/scenario-runs", response_model=ValidationScenarioRunRead)
async def scenario_result(campaign_id: UUID, payload: ValidationScenarioResultCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ValidationScenarioRunRead.model_validate(await service.record_scenario_result(db, actor, campaign_id, **payload.model_dump()))


@router.post("/scenario-runs/{scenario_run_id}/evidence", response_model=ValidationEvidenceRead, status_code=201)
async def add_evidence(scenario_run_id: UUID, payload: ValidationEvidenceCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ValidationEvidenceRead.model_validate(await service.add_evidence(db, actor, scenario_run_id, **payload.model_dump()))


@router.patch("/campaigns/{campaign_id}/checks/{check_id}", response_model=PilotReadinessRead)
async def update_check(campaign_id: UUID, check_id: UUID, payload: PilotReadinessUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return PilotReadinessRead.model_validate(await service.update_pilot_check(db, actor, campaign_id, check_id, **payload.model_dump()))


@router.post("/campaigns/{campaign_id}/datasets", response_model=ValidationDatasetRead, status_code=201)
async def add_dataset(campaign_id: UUID, payload: ValidationDatasetCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ValidationDatasetRead.model_validate(await service.add_dataset(db, actor, campaign_id, **payload.model_dump()))


@router.post("/campaigns/{campaign_id}/signoffs", response_model=ValidationSignoffRead)
async def signoff(campaign_id: UUID, payload: ValidationSignoffCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ValidationSignoffRead.model_validate(await service.signoff(db, actor, campaign_id, **payload.model_dump()))


@router.post("/campaigns/{campaign_id}/evaluate")
async def evaluate(campaign_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.evaluate_campaign(db, actor, campaign_id)
    return {"campaign": ValidationCampaignRead.model_validate(raw["campaign"]), "manifest": ReleaseCandidateManifestRead.model_validate(raw["manifest"]), "gate": raw["gate"]}
