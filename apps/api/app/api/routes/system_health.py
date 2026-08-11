from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.jobs import JobKind, JobPriority
from app.models.system_health import HealthTrigger
from app.schemas.jobs import JobRead
from app.schemas.system_health import (
    BackupPolicyCreate,
    BackupPolicyRead,
    BackupPolicyUpdate,
    BackupRunDetail,
    BackupRunRead,
    HealthRunDetail,
    IncidentRead,
    IncidentUpdate,
    RecoveryObjectiveRead,
    RecoveryObjectiveUpdate,
    RestoreDrillRead,
    RestoreDrillReview,
    SystemHealthDashboard,
)
from app.services.jobs import service as jobs_service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor
from app.services.system_health import service
from app.services.system_health import scheduler

router = APIRouter(prefix="/system-health", tags=["system-health"])


@router.post("/scheduler/tick")
async def scheduler_tick(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    # Scheduling changes operational work, so only firm managers can trigger a tick.
    if actor.role.value not in {"owner", "admin", "partner"}:
        raise HTTPException(403, "Firm manager role required")
    # Uses the caller organization, but scheduled jobs are owned by a durable manager membership.
    return await scheduler.tick(db, actor.organization_id)


@router.get("/dashboard", response_model=SystemHealthDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.dashboard(db, actor)
    return SystemHealthDashboard(**raw)


@router.post("/checks/run", response_model=HealthRunDetail)
async def run_checks(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.run_health_checks(db, actor, trigger=HealthTrigger.MANUAL)
    return HealthRunDetail(**raw)


@router.get("/checks/{run_id}", response_model=HealthRunDetail)
async def check_detail(run_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return HealthRunDetail(**(await service.health_run_detail(db, actor, run_id)))


@router.get("/incidents", response_model=list[IncidentRead])
async def incidents(include_resolved: bool = False, limit: int = Query(100, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [IncidentRead.model_validate(row) for row in await service.list_incidents(db, actor, include_resolved=include_resolved, limit=limit)]


@router.patch("/incidents/{incident_id}", response_model=IncidentRead)
async def patch_incident(incident_id: UUID, payload: IncidentUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return IncidentRead.model_validate(await service.update_incident(db, actor, incident_id, action=payload.action, note=payload.note))


@router.get("/recovery-objectives", response_model=RecoveryObjectiveRead)
async def recovery_objectives(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return RecoveryObjectiveRead.model_validate(await service.get_or_create_objectives(db, actor))


@router.patch("/recovery-objectives", response_model=RecoveryObjectiveRead)
async def patch_recovery_objectives(payload: RecoveryObjectiveUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return RecoveryObjectiveRead.model_validate(await service.update_objectives(db, actor, payload.model_dump(exclude_unset=True)))


@router.get("/backups/policies", response_model=list[BackupPolicyRead])
async def backup_policies(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [BackupPolicyRead.model_validate(row) for row in await service.list_backup_policies(db, actor)]


@router.post("/backups/policies/default", response_model=BackupPolicyRead)
async def default_backup_policy(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return BackupPolicyRead.model_validate(await service.create_default_backup_policy(db, actor))


@router.post("/backups/policies", response_model=BackupPolicyRead, status_code=201)
async def create_backup_policy(payload: BackupPolicyCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return BackupPolicyRead.model_validate(await service.create_backup_policy(db, actor, payload.model_dump()))


@router.patch("/backups/policies/{policy_id}", response_model=BackupPolicyRead)
async def patch_backup_policy(policy_id: UUID, payload: BackupPolicyUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return BackupPolicyRead.model_validate(await service.update_backup_policy(db, actor, policy_id, payload.model_dump(exclude_unset=True)))


@router.post("/backups/policies/{policy_id}/run", response_model=JobRead, status_code=202)
async def queue_backup(policy_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row = await jobs_service.enqueue(
        db,
        actor,
        kind=JobKind.BACKUP_RUN,
        payload={"policy_id": str(policy_id)},
        priority=JobPriority.HIGH,
        resource_type="backup_policy",
        resource_id=policy_id,
        idempotency_key=None,
    )
    return JobRead.model_validate(row)


@router.get("/backups/runs", response_model=list[BackupRunRead])
async def backup_runs(limit: int = Query(30, ge=1, le=200), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [BackupRunRead.model_validate(row) for row in await service.list_backup_runs(db, actor, limit=limit)]


@router.get("/backups/runs/{run_id}", response_model=BackupRunDetail)
async def backup_run(run_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.backup_run_detail(db, actor, run_id)
    return BackupRunDetail(run=BackupRunRead.model_validate(raw["run"]), artifacts=raw["artifacts"])


@router.post("/backups/runs/{run_id}/verify", response_model=JobRead, status_code=202)
async def queue_restore_verification(run_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row = await jobs_service.enqueue(
        db,
        actor,
        kind=JobKind.RESTORE_VERIFY,
        payload={"backup_run_id": str(run_id)},
        priority=JobPriority.HIGH,
        resource_type="backup_run",
        resource_id=run_id,
    )
    return JobRead.model_validate(row)


@router.get("/restore-drills", response_model=list[RestoreDrillRead])
async def restore_drills(limit: int = Query(30, ge=1, le=200), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [RestoreDrillRead.model_validate(row) for row in await service.list_restore_drills(db, actor, limit=limit)]


@router.post("/restore-drills/{drill_id}/review", response_model=RestoreDrillRead)
async def review_restore_drill(drill_id: UUID, payload: RestoreDrillReview, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return RestoreDrillRead.model_validate(await service.review_restore_drill(db, actor, drill_id, notes=payload.notes))
