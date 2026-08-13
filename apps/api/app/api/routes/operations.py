from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.operations import WorkflowTaskStatus
from app.schemas.operations import (
    AgendaItem, CourtChangeRead, CourtSnapshotCaptureRead, CourtSnapshotCreate, CourtSnapshotRead,
    CourtSourceCapabilityRead, CourtTrackerCreate, CourtTrackerRead, NotificationRead,
    OperationsDashboard, OperationsPreferenceRead, OperationsPreferenceUpdate, SweepRequest,
    SupervisionSummary, TemplateSeedResult, WorkflowTaskCreate, WorkflowTaskRead, WorkflowTaskUpdate, WorkflowTemplateRead,
)
from app.services.operations import service
from app.services.operations.providers import source_capabilities
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/operations", tags=["workflow-and-court-operations"])


@router.get("/dashboard", response_model=OperationsDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return OperationsDashboard(**await service.dashboard(db, actor))


@router.get("/agenda", response_model=list[AgendaItem])
async def agenda(days: int = Query(7, ge=1, le=90), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [AgendaItem(**item) for item in await service.daily_agenda(db, actor, days)]


@router.get("/supervision", response_model=SupervisionSummary)
async def supervision(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SupervisionSummary.model_validate(await service.partner_supervision(db, actor))


@router.post("/templates/seed", response_model=TemplateSeedResult)
async def seed_templates(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return TemplateSeedResult(created=await service.seed_builtin_templates(db))


@router.get("/templates", response_model=list[WorkflowTemplateRead])
async def templates(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [WorkflowTemplateRead.model_validate(row) for row in await service.list_templates(db, actor)]


@router.get("/court-sources", response_model=list[CourtSourceCapabilityRead])
async def court_sources():
    return [CourtSourceCapabilityRead(source_kind=item.source_kind, automatic_fetch=item.automatic_fetch, requires_user_or_approved_connector=item.requires_user_or_approved_connector, note=item.note) for item in source_capabilities()]


@router.get("/tasks", response_model=list[WorkflowTaskRead])
async def tasks(
    status: WorkflowTaskStatus | None = None,
    assigned_to_me: bool = False,
    limit: int = Query(200, ge=1, le=1000),
    actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db),
):
    rows = await service.list_tasks(db, actor, status=status, assigned_to_me=assigned_to_me, limit=limit)
    return [WorkflowTaskRead.model_validate(row) for row in rows]


@router.post("/tasks", response_model=WorkflowTaskRead, status_code=201)
async def create_task(payload: WorkflowTaskCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return WorkflowTaskRead.model_validate(await service.create_task(db, actor, payload))


@router.patch("/tasks/{task_id}", response_model=WorkflowTaskRead)
async def patch_task(task_id: UUID, payload: WorkflowTaskUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return WorkflowTaskRead.model_validate(await service.update_task(db, actor, task_id, payload))


@router.post("/sweep")
async def sweep(payload: SweepRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.run_due_sweep(db, actor, payload)


@router.get("/notifications", response_model=list[NotificationRead])
async def notifications(
    unread_only: bool = False, limit: int = Query(100, ge=1, le=500),
    actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db),
):
    return [NotificationRead.model_validate(row) for row in await service.list_notifications(db, actor, unread_only=unread_only, limit=limit)]


@router.post("/notifications/process")
async def process_notifications(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.mark_notifications_sent(db, actor)


@router.get("/preferences", response_model=OperationsPreferenceRead)
async def preferences(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return OperationsPreferenceRead.model_validate(await service.get_preferences(db, actor))


@router.patch("/preferences", response_model=OperationsPreferenceRead)
async def patch_preferences(payload: OperationsPreferenceUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return OperationsPreferenceRead.model_validate(await service.update_preferences(db, actor, payload))


@router.get("/trackers", response_model=list[CourtTrackerRead])
async def trackers(matter_id: UUID | None = None, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [CourtTrackerRead.model_validate(row) for row in await service.list_trackers(db, actor, matter_id)]


@router.post("/trackers", response_model=CourtTrackerRead, status_code=201)
async def create_tracker(payload: CourtTrackerCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return CourtTrackerRead.model_validate(await service.create_tracker(db, actor, payload))


@router.post("/trackers/{tracker_id}/snapshots", response_model=CourtSnapshotCaptureRead, status_code=201)
async def capture_snapshot(tracker_id: UUID, payload: CourtSnapshotCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    snapshot, changes = await service.capture_snapshot(db, actor, tracker_id, payload)
    return CourtSnapshotCaptureRead(
        snapshot=CourtSnapshotRead.model_validate(snapshot),
        changes=[CourtChangeRead.model_validate(row) for row in changes],
    )


@router.get("/trackers/{tracker_id}/snapshots", response_model=list[CourtSnapshotRead])
async def snapshots(tracker_id: UUID, limit: int = Query(50, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [CourtSnapshotRead.model_validate(row) for row in await service.list_snapshots(db, actor, tracker_id, limit)]


@router.get("/court-changes", response_model=list[CourtChangeRead])
async def court_changes(
    matter_id: UUID | None = None, unreviewed_only: bool = False, limit: int = Query(100, ge=1, le=500),
    actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db),
):
    return [CourtChangeRead.model_validate(row) for row in await service.list_changes(db, actor, matter_id=matter_id, unreviewed_only=unreviewed_only, limit=limit)]


@router.post("/court-changes/{change_id}/review", response_model=CourtChangeRead)
async def review_change(change_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return CourtChangeRead.model_validate(await service.review_change(db, actor, change_id))
