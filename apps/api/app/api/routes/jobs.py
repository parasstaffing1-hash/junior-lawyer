from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.jobs import JobStatus
from app.schemas.jobs import JobCreate, JobDetail, JobRead, JobsDashboard, QueueRead, QueueUpdate
from app.services.jobs import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/jobs", tags=["background-jobs"])


@router.get("/dashboard", response_model=JobsDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.dashboard(db, actor)
    return JobsDashboard(**raw)


@router.get("/queues", response_model=list[QueueRead])
async def queues(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [QueueRead.model_validate(row) for row in await service.list_queues(db,actor)]


@router.patch("/queues/{queue_id}", response_model=QueueRead)
async def patch_queue(queue_id: UUID, payload: QueueUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return QueueRead.model_validate(await service.update_queue(db,actor,queue_id,payload.model_dump(exclude_unset=True)))


@router.get("", response_model=list[JobRead])
async def jobs(status: JobStatus | None = None, queue: str | None = None, limit: int = Query(100, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [JobRead.model_validate(row) for row in await service.list_jobs(db, actor, status=status, queue=queue, limit=limit)]


@router.post("", response_model=JobRead, status_code=201)
async def create_job(payload: JobCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row = await service.enqueue(db, actor, kind=payload.kind, payload=payload.payload, priority=payload.priority,
        queue_name=payload.queue_name, matter_id=payload.matter_id, resource_type=payload.resource_type,
        resource_id=payload.resource_id, idempotency_key=payload.idempotency_key,
        max_attempts=payload.max_attempts, scheduled_at=payload.scheduled_at, depends_on=payload.depends_on)
    return JobRead.model_validate(row)


@router.get("/{job_id}", response_model=JobDetail)
async def job_detail(job_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    raw = await service.job_detail(db, actor, job_id)
    return JobDetail(job=JobRead.model_validate(raw["job"]), attempts=raw["attempts"], events=raw["events"], artifacts=raw["artifacts"])


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel(job_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return JobRead.model_validate(await service.request_cancel(db, actor, job_id))


@router.post("/{job_id}/retry", response_model=JobRead)
async def retry(job_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return JobRead.model_validate(await service.retry_job(db, actor, job_id))
