from __future__ import annotations

import os
import socket
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import (
    BackgroundJob, BackgroundJobArtifact, BackgroundJobAttempt, BackgroundJobDependency,
    BackgroundJobEvent, BackgroundQueue, BackgroundWorker, JobAttemptStatus, JobEventLevel,
    JobKind, JobPriority, JobStatus, WorkerStatus,
)
from app.models.document import Document
from app.models.evidence import EvidenceBundle
from app.models.security import OrganizationRole, MatterAccessLevel, DocumentAccessLevel
from app.services.security.permissions import decide_document_access, decide_matter_access
from app.services.jobs.engine import PRIORITY_VALUE, can_retry, progress_percent, retry_at, utcnow
from app.services.jobs.handlers import execute_handler
from app.services.security.context import ActorContext, reset_current_actor, set_current_actor

MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}
DEFAULT_QUEUE_BY_KIND = {
    JobKind.DOCUMENT_REPROCESS: "documents",
    JobKind.SEARCH_DOCUMENT_REINDEX: "search",
    JobKind.SEARCH_ORG_REBUILD: "search",
    JobKind.SEARCH_DUPLICATE_SCAN: "search",
    JobKind.MATTER_INTELLIGENCE_REBUILD: "evidence",
    JobKind.EVIDENCE_MATTER_REBUILD: "evidence",
    JobKind.ANALYTICS_SNAPSHOT: "analytics",
    JobKind.ANALYTICS_RISK_REBUILD: "analytics",
    JobKind.OPERATIONS_DUE_SWEEP: "operations",
    JobKind.CORPUS_RESOLVE_CITATIONS: "corpus",
    JobKind.LEGAL_DATA_FEED_SYNC: "corpus",
    JobKind.LEGAL_DATA_INTEGRITY_SWEEP: "corpus",
    JobKind.EVIDENCE_BUNDLE_BUILD: "bundles",
    JobKind.EVIDENCE_BUNDLE_FINALIZE: "bundles",
    JobKind.SYSTEM_HEALTH_CHECK: "maintenance",
    JobKind.BACKUP_RUN: "maintenance",
    JobKind.RESTORE_VERIFY: "maintenance",
}


def _require_manager(actor: ActorContext) -> None:
    if actor.role not in MANAGER_ROLES:
        raise HTTPException(403, "Partner, admin or owner role required")


async def _authorize_and_normalize_job(db: AsyncSession, actor: ActorContext, kind: JobKind, payload: dict, matter_id: UUID | None) -> UUID | None:
    manager_only = {JobKind.SEARCH_ORG_REBUILD, JobKind.SEARCH_DUPLICATE_SCAN, JobKind.ANALYTICS_SNAPSHOT, JobKind.ANALYTICS_RISK_REBUILD, JobKind.OPERATIONS_DUE_SWEEP, JobKind.CORPUS_RESOLVE_CITATIONS, JobKind.LEGAL_DATA_FEED_SYNC, JobKind.LEGAL_DATA_INTEGRITY_SWEEP, JobKind.SYSTEM_HEALTH_CHECK, JobKind.BACKUP_RUN, JobKind.RESTORE_VERIFY}
    if kind in manager_only:
        _require_manager(actor)
    if kind in {JobKind.DOCUMENT_REPROCESS, JobKind.SEARCH_DOCUMENT_REINDEX}:
        raw = payload.get("document_id")
        if not raw: raise HTTPException(422, "document_id is required")
        doc = await db.get(Document, UUID(str(raw)))
        if not doc: raise HTTPException(404, "Document not found")
        decision = await decide_document_access(db, actor, doc.id, required=DocumentAccessLevel.EDIT if kind == JobKind.DOCUMENT_REPROCESS else DocumentAccessLevel.VIEW)
        if not decision.allowed: raise HTTPException(403, decision.reason)
        return doc.matter_id
    if kind in {JobKind.MATTER_INTELLIGENCE_REBUILD, JobKind.EVIDENCE_MATTER_REBUILD}:
        mid = UUID(str(payload.get("matter_id") or matter_id)) if (payload.get("matter_id") or matter_id) else None
        if not mid: raise HTTPException(422, "matter_id is required")
        decision = await decide_matter_access(db, actor, mid, required=MatterAccessLevel.WORK)
        if not decision.allowed: raise HTTPException(403, decision.reason)
        payload["matter_id"] = str(mid); return mid
    if kind == JobKind.EVIDENCE_BUNDLE_BUILD:
        mid = UUID(str(payload.get("matter_id") or matter_id)) if (payload.get("matter_id") or matter_id) else None
        if not mid: raise HTTPException(422,"matter_id is required")
        decision=await decide_matter_access(db,actor,mid,required=MatterAccessLevel.WORK)
        if not decision.allowed or decision.export_allowed is False: raise HTTPException(403,decision.reason if not decision.allowed else "Exports are disabled for this matter")
        payload["matter_id"]=str(mid); return mid
    if kind == JobKind.EVIDENCE_BUNDLE_FINALIZE:
        raw = payload.get("bundle_id")
        if not raw: raise HTTPException(422, "bundle_id is required")
        bundle = await db.get(EvidenceBundle, UUID(str(raw)))
        if not bundle: raise HTTPException(404, "Bundle not found")
        decision = await decide_matter_access(db, actor, bundle.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed or decision.export_allowed is False: raise HTTPException(403, decision.reason if not decision.allowed else "Exports are disabled for this matter")
        return bundle.matter_id
    if kind == JobKind.LEGAL_DATA_FEED_SYNC:
        if not payload.get("feed_id"):
            raise HTTPException(422, "feed_id is required")
    if kind == JobKind.BACKUP_RUN:
        if not payload.get("policy_id"):
            raise HTTPException(422, "policy_id is required")
    if kind == JobKind.RESTORE_VERIFY:
        if not payload.get("backup_run_id"):
            raise HTTPException(422, "backup_run_id is required")
    if matter_id:
        decision = await decide_matter_access(db, actor, matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed: raise HTTPException(403, decision.reason)
    return matter_id


async def ensure_default_queues(db: AsyncSession, organization_id: UUID) -> None:
    names = {"default", *DEFAULT_QUEUE_BY_KIND.values()}
    existing = set((await db.scalars(select(BackgroundQueue.name).where(BackgroundQueue.organization_id == organization_id))).all())
    for name in sorted(names - existing):
        db.add(BackgroundQueue(organization_id=organization_id, name=name, max_concurrency=2 if name in {"documents", "bundles"} else 4, max_per_minute=60 if name in {"documents", "bundles"} else 180))
    await db.commit()


async def list_queues(db: AsyncSession, actor: ActorContext) -> list[BackgroundQueue]:
    await ensure_default_queues(db, actor.organization_id)
    return list((await db.scalars(select(BackgroundQueue).where(BackgroundQueue.organization_id==actor.organization_id).order_by(BackgroundQueue.name))).all())


async def update_queue(db: AsyncSession, actor: ActorContext, queue_id: UUID, values: dict) -> BackgroundQueue:
    _require_manager(actor)
    row=await db.get(BackgroundQueue,queue_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404,"Queue not found")
    for k,v in values.items():
        if v is not None and hasattr(row,k): setattr(row,k,v)
    await db.commit(); await db.refresh(row); return row


async def enqueue(db: AsyncSession, actor: ActorContext, *, kind: JobKind, payload: dict, priority: JobPriority = JobPriority.NORMAL,
                  queue_name: str | None = None, matter_id: UUID | None = None, resource_type: str | None = None,
                  resource_id: UUID | None = None, idempotency_key: str | None = None, max_attempts: int | None = None,
                  scheduled_at=None, depends_on: list[UUID] | None = None) -> BackgroundJob:
    payload = dict(payload or {})
    matter_id = await _authorize_and_normalize_job(db, actor, kind, payload, matter_id)
    await ensure_default_queues(db, actor.organization_id)
    if idempotency_key:
        idempotency_key=f"{actor.membership_id}:{idempotency_key}"
        existing = await db.scalar(select(BackgroundJob).where(BackgroundJob.organization_id == actor.organization_id, BackgroundJob.idempotency_key == idempotency_key))
        if existing:
            return existing
    qname = queue_name or DEFAULT_QUEUE_BY_KIND.get(kind, "default")
    q = await db.scalar(select(BackgroundQueue).where(BackgroundQueue.organization_id == actor.organization_id, BackgroundQueue.name == qname))
    if not q or not q.enabled:
        raise HTTPException(409, f"Queue '{qname}' is disabled")
    row = BackgroundJob(
        organization_id=actor.organization_id, requested_by_membership_id=actor.membership_id,
        queue_name=qname, kind=kind, status=JobStatus.QUEUED, priority=priority,
        priority_value=PRIORITY_VALUE[priority], matter_id=matter_id, resource_type=resource_type,
        resource_id=resource_id, payload_json=payload, idempotency_key=idempotency_key,
        max_attempts=max_attempts or q.default_max_attempts, scheduled_at=scheduled_at or utcnow(),
        progress_total=100, progress_current=0, progress_message="Queued",
    )
    db.add(row); await db.flush()
    for dep in depends_on or []:
        if dep == row.id: raise HTTPException(422, "A job cannot depend on itself")
        dependency=await db.get(BackgroundJob,dep)
        if not dependency or dependency.organization_id != actor.organization_id: raise HTTPException(422,"Dependency must belong to the same organization")
        db.add(BackgroundJobDependency(job_id=row.id, depends_on_job_id=dep, required_status=JobStatus.SUCCEEDED))
    db.add(BackgroundJobEvent(job_id=row.id, event_type="queued", message="Job queued", progress_current=0, progress_total=100))
    await db.commit(); await db.refresh(row); return row


async def list_jobs(db: AsyncSession, actor: ActorContext, *, status: JobStatus | None = None, queue: str | None = None, limit: int = 100) -> list[BackgroundJob]:
    stmt = select(BackgroundJob).where(BackgroundJob.organization_id == actor.organization_id)
    if status: stmt = stmt.where(BackgroundJob.status == status)
    if queue: stmt = stmt.where(BackgroundJob.queue_name == queue)
    candidates=list((await db.scalars(stmt.order_by(BackgroundJob.created_at.desc()).limit(max(limit*3,limit)))).all())
    result=[]
    for row in candidates:
        if actor.role not in MANAGER_ROLES and row.requested_by_membership_id != actor.membership_id:
            continue
        if row.matter_id:
            decision=await decide_matter_access(db,actor,row.matter_id,required=MatterAccessLevel.VIEW)
            if not decision.allowed: continue
        result.append(row)
        if len(result)>=limit: break
    return result


async def get_job(db: AsyncSession, actor: ActorContext, job_id: UUID) -> BackgroundJob:
    row = await db.get(BackgroundJob, job_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Job not found")
    if actor.role not in MANAGER_ROLES and row.requested_by_membership_id != actor.membership_id: raise HTTPException(404, "Job not found")
    if row.matter_id:
        decision=await decide_matter_access(db,actor,row.matter_id,required=MatterAccessLevel.VIEW)
        if not decision.allowed: raise HTTPException(404, "Job not found")
    return row


async def request_cancel(db: AsyncSession, actor: ActorContext, job_id: UUID) -> BackgroundJob:
    row = await get_job(db, actor, job_id)
    if row.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.DEAD_LETTER}: return row
    row.cancellation_requested_at = utcnow()
    if row.status in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
        row.status = JobStatus.CANCELLED; row.finished_at = utcnow(); row.progress_message = "Cancelled before execution"
    db.add(BackgroundJobEvent(job_id=row.id, event_type="cancel_requested", level=JobEventLevel.WARNING, message="Cancellation requested"))
    await db.commit(); await db.refresh(row); return row


async def retry_job(db: AsyncSession, actor: ActorContext, job_id: UUID) -> BackgroundJob:
    _require_manager(actor)
    row = await get_job(db, actor, job_id)
    if row.status not in {JobStatus.FAILED, JobStatus.DEAD_LETTER, JobStatus.CANCELLED}: raise HTTPException(409, "Only failed, dead-lettered or cancelled jobs can be retried")
    row.status = JobStatus.QUEUED; row.scheduled_at = utcnow(); row.finished_at = None; row.cancellation_requested_at = None; row.last_error = None; row.progress_current = 0; row.progress_message = "Requeued manually"
    db.add(BackgroundJobEvent(job_id=row.id, event_type="manual_retry", message="Job requeued manually"))
    await db.commit(); await db.refresh(row); return row


async def register_worker(db: AsyncSession, organization_id: UUID, worker_key: str, queues: list[str]) -> BackgroundWorker:
    now = utcnow(); row = await db.scalar(select(BackgroundWorker).where(BackgroundWorker.organization_id == organization_id, BackgroundWorker.worker_key == worker_key))
    if row:
        row.hostname=socket.gethostname(); row.pid=os.getpid(); row.status=WorkerStatus.ONLINE; row.queues_json=queues; row.heartbeat_at=now; row.current_job_id=None
    else:
        row=BackgroundWorker(organization_id=organization_id, worker_key=worker_key, hostname=socket.gethostname(), pid=os.getpid(), status=WorkerStatus.ONLINE, queues_json=queues, started_at=now, heartbeat_at=now)
        db.add(row)
    await db.commit(); await db.refresh(row); return row


async def heartbeat(db: AsyncSession, worker: BackgroundWorker, current_job_id: UUID | None = None) -> None:
    worker.heartbeat_at=utcnow(); worker.current_job_id=current_job_id; await db.commit()


async def requeue_expired_leases(db: AsyncSession, organization_id: UUID | None = None) -> int:
    now=utcnow(); stmt=select(BackgroundJob).where(BackgroundJob.status.in_([JobStatus.LEASED, JobStatus.RUNNING]), BackgroundJob.lease_expires_at.is_not(None), BackgroundJob.lease_expires_at < now)
    if organization_id: stmt=stmt.where(BackgroundJob.organization_id==organization_id)
    rows=list((await db.scalars(stmt)).all())
    for row in rows:
        attempt=await db.scalar(select(BackgroundJobAttempt).where(BackgroundJobAttempt.job_id==row.id,BackgroundJobAttempt.attempt_number==row.attempt_count))
        if attempt and attempt.status in {JobAttemptStatus.LEASED,JobAttemptStatus.RUNNING}: attempt.status=JobAttemptStatus.ABANDONED; attempt.finished_at=now; attempt.error_message="Worker lease expired"
        row.lease_id=None; row.leased_by_worker_id=None; row.lease_expires_at=None
        if row.cancellation_requested_at:
            row.status=JobStatus.CANCELLED; row.finished_at=now; row.progress_message="Cancelled after lease expiry"
        elif can_retry(row.attempt_count, row.max_attempts):
            row.status=JobStatus.RETRY_WAIT; row.scheduled_at=retry_at(now, row.attempt_count, row.backoff_base_seconds); row.progress_message="Worker lease expired; waiting to retry"
        else:
            row.status=JobStatus.DEAD_LETTER; row.finished_at=now; row.progress_message="Dead-lettered after worker lease expiry"
        db.add(BackgroundJobEvent(job_id=row.id,event_type="lease_expired",level=JobEventLevel.WARNING,message=row.progress_message))
    if rows: await db.commit()
    return len(rows)


async def _dependency_state(db: AsyncSession, job_id: UUID) -> str:
    deps=list((await db.execute(select(BackgroundJobDependency, BackgroundJob.status).join(BackgroundJob, BackgroundJob.id==BackgroundJobDependency.depends_on_job_id).where(BackgroundJobDependency.job_id==job_id))).all())
    if not deps: return "ready"
    impossible={JobStatus.FAILED,JobStatus.CANCELLED,JobStatus.DEAD_LETTER}
    if any(status in impossible for _,status in deps): return "impossible"
    if all(status == dep.required_status for dep,status in deps): return "ready"
    return "waiting"


async def claim_next(db: AsyncSession, worker: BackgroundWorker, queues: list[str]) -> BackgroundJob | None:
    await requeue_expired_leases(db,worker.organization_id); now=utcnow()
    stmt=(select(BackgroundJob).where(BackgroundJob.organization_id==worker.organization_id, BackgroundJob.queue_name.in_(queues), BackgroundJob.status.in_([JobStatus.QUEUED, JobStatus.RETRY_WAIT]), BackgroundJob.scheduled_at <= now, BackgroundJob.cancellation_requested_at.is_(None)).order_by(BackgroundJob.priority_value.desc(), BackgroundJob.scheduled_at.asc(), BackgroundJob.created_at.asc()).limit(25))
    if db.bind and db.bind.dialect.name == "postgresql": stmt=stmt.with_for_update(skip_locked=True)
    for row in list((await db.scalars(stmt)).all()):
        dep_state=await _dependency_state(db,row.id)
        if dep_state == "waiting": continue
        if dep_state == "impossible":
            row.status=JobStatus.DEAD_LETTER; row.finished_at=now; row.progress_message="Dependency did not succeed"
            db.add(BackgroundJobEvent(job_id=row.id,event_type="dependency_failed",level=JobEventLevel.ERROR,message="Required dependency did not succeed")); await db.commit(); continue
        qstmt=select(BackgroundQueue).where(BackgroundQueue.organization_id==row.organization_id,BackgroundQueue.name==row.queue_name)
        if db.bind and db.bind.dialect.name == "postgresql": qstmt=qstmt.with_for_update()
        q=await db.scalar(qstmt)
        if q and not q.enabled: continue
        if q:
            active=await db.scalar(select(func.count()).select_from(BackgroundJob).where(BackgroundJob.organization_id==row.organization_id,BackgroundJob.queue_name==row.queue_name,BackgroundJob.status.in_([JobStatus.LEASED,JobStatus.RUNNING])))
            if int(active or 0) >= max(1,q.max_concurrency): continue
            recent=await db.scalar(select(func.count()).select_from(BackgroundJobAttempt).join(BackgroundJob,BackgroundJob.id==BackgroundJobAttempt.job_id).where(BackgroundJob.organization_id==row.organization_id,BackgroundJob.queue_name==row.queue_name,BackgroundJobAttempt.leased_at >= now-timedelta(minutes=1)))
            if int(recent or 0) >= max(1,q.max_per_minute): continue
        lease_seconds=q.lease_seconds if q else 300
        row.status=JobStatus.LEASED; row.leased_by_worker_id=worker.id; row.lease_id=uuid4(); row.lease_expires_at=now+timedelta(seconds=lease_seconds); row.attempt_count+=1; row.progress_message="Leased by worker"
        attempt=BackgroundJobAttempt(job_id=row.id,worker_id=worker.id,attempt_number=row.attempt_count,status=JobAttemptStatus.LEASED,leased_at=now)
        db.add(attempt); db.add(BackgroundJobEvent(job_id=row.id,event_type="leased",message=f"Leased by {worker.worker_key}")); await db.commit(); await db.refresh(row); return row
    return None


async def renew_lease(db: AsyncSession, worker_id: UUID, job_id: UUID) -> bool:
    job=await db.get(BackgroundJob,job_id)
    worker=await db.get(BackgroundWorker,worker_id)
    if not job or not worker or job.leased_by_worker_id != worker_id or job.status not in {JobStatus.LEASED,JobStatus.RUNNING}: return False
    q=await db.scalar(select(BackgroundQueue).where(BackgroundQueue.organization_id==job.organization_id,BackgroundQueue.name==job.queue_name))
    job.lease_expires_at=utcnow()+timedelta(seconds=q.lease_seconds if q else 300); worker.heartbeat_at=utcnow(); worker.current_job_id=job.id
    await db.commit(); return True


async def set_progress(db: AsyncSession, job: BackgroundJob, current: int, total: int, message: str) -> None:
    job.progress_current=current; job.progress_total=max(1,total); job.progress_message=message
    db.add(BackgroundJobEvent(job_id=job.id,event_type="progress",message=message,progress_current=current,progress_total=total))
    await db.commit()


async def execute_claimed(db: AsyncSession, worker: BackgroundWorker, job: BackgroundJob) -> BackgroundJob:
    if job.leased_by_worker_id != worker.id: raise RuntimeError("Job is not leased by this worker")
    now=utcnow(); attempt=await db.scalar(select(BackgroundJobAttempt).where(BackgroundJobAttempt.job_id==job.id,BackgroundJobAttempt.attempt_number==job.attempt_count))
    if job.cancellation_requested_at:
        job.status=JobStatus.CANCELLED; job.finished_at=now; job.progress_message="Cancelled"; attempt.status=JobAttemptStatus.CANCELLED; attempt.finished_at=now; await db.commit(); return job
    job.status=JobStatus.RUNNING; job.started_at=job.started_at or now; job.progress_message="Running"
    attempt.status=JobAttemptStatus.RUNNING; attempt.started_at=now; worker.current_job_id=job.id; worker.heartbeat_at=now
    db.add(BackgroundJobEvent(job_id=job.id,event_type="started",message="Execution started",progress_current=1,progress_total=100)); await db.commit()
    try:
        # Handlers reconstruct the initiating actor and re-run current permission checks.
        result = await execute_handler(db, job)
        await db.refresh(job)
        if job.cancellation_requested_at:
            db.add(BackgroundJobEvent(job_id=job.id,event_type="cancel_too_late",level=JobEventLevel.WARNING,message="Cancellation was requested after execution had already begun; completed output was preserved"))
        if isinstance(result,dict) and result.get("storage_key"):
            db.add(BackgroundJobArtifact(job_id=job.id,kind=job.resource_type or "output",storage_key=str(result.get("storage_key")),sha256=str(result.get("sha256")) if result.get("sha256") else None,metadata_json={"handler":job.kind.value}))
        job.status=JobStatus.SUCCEEDED; job.result_json=result or {}; job.finished_at=utcnow(); job.progress_current=100; job.progress_total=100; job.progress_message="Completed"; job.lease_expires_at=None; job.lease_id=None
        attempt.status=JobAttemptStatus.SUCCEEDED; attempt.finished_at=job.finished_at; worker.jobs_succeeded+=1; worker.current_job_id=None
        db.add(BackgroundJobEvent(job_id=job.id,event_type="succeeded",message="Job completed",progress_current=100,progress_total=100)); await db.commit(); await db.refresh(job); return job
    except Exception as exc:
        now=utcnow(); msg=f"{type(exc).__name__}: {exc}"[:8000]; job.last_error=msg; attempt.status=JobAttemptStatus.FAILED; attempt.finished_at=now; attempt.error_type=type(exc).__name__; attempt.error_message=str(exc)[:8000]; worker.jobs_failed+=1; worker.current_job_id=None; job.lease_expires_at=None; job.lease_id=None
        if job.cancellation_requested_at:
            job.status=JobStatus.CANCELLED; job.finished_at=now; job.progress_message="Cancelled"
        elif can_retry(job.attempt_count,job.max_attempts):
            job.status=JobStatus.RETRY_WAIT; job.scheduled_at=retry_at(now,job.attempt_count,job.backoff_base_seconds); job.progress_message="Retry scheduled"
        else:
            job.status=JobStatus.DEAD_LETTER; job.finished_at=now; job.progress_message="Dead-lettered"
        db.add(BackgroundJobEvent(job_id=job.id,event_type="failed",level=JobEventLevel.ERROR,message=msg)); await db.commit(); await db.refresh(job); return job


async def job_detail(db: AsyncSession, actor: ActorContext, job_id: UUID) -> dict:
    row=await get_job(db,actor,job_id)
    attempts=list((await db.scalars(select(BackgroundJobAttempt).where(BackgroundJobAttempt.job_id==job_id).order_by(BackgroundJobAttempt.attempt_number.desc()))).all())
    events=list((await db.scalars(select(BackgroundJobEvent).where(BackgroundJobEvent.job_id==job_id).order_by(BackgroundJobEvent.created_at.desc()).limit(100))).all())
    artifacts=list((await db.scalars(select(BackgroundJobArtifact).where(BackgroundJobArtifact.job_id==job_id).order_by(BackgroundJobArtifact.created_at.desc()))).all())
    return {"job":row,"attempts":attempts,"events":events,"artifacts":artifacts}


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    rows=await list_jobs(db,actor,limit=5000)
    by_status={s.value:0 for s in JobStatus}; by_queue={}
    for r in rows: by_status[r.status.value]=by_status.get(r.status.value,0)+1; by_queue[r.queue_name]=by_queue.get(r.queue_name,0)+1
    workers=list((await db.scalars(select(BackgroundWorker).where(BackgroundWorker.organization_id==actor.organization_id).order_by(BackgroundWorker.heartbeat_at.desc()).limit(100))).all()) if actor.role in MANAGER_ROLES else []
    now=utcnow(); online=[w for w in workers if w.status==WorkerStatus.ONLINE and (now-w.heartbeat_at).total_seconds()<90]
    return {"total":len(rows),"by_status":by_status,"by_queue":by_queue,"online_workers":len(online),"workers":workers[:20],"dead_letter":by_status.get(JobStatus.DEAD_LETTER.value,0)}

