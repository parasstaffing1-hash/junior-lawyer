from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import SnapshotKind
from app.models.jobs import BackgroundJob, JobKind
from app.models.security import MembershipStatus, OrganizationMembership, SecurityUser
from app.schemas.evidence import BundleCreate
from app.schemas.operations import SweepRequest
from app.services.analytics import service as analytics_service
from app.services.documents import service as document_service
from app.services.evidence import service as evidence_service
from app.services.intelligence.service import rebuild_matter_intelligence
from app.services.legal_data import service as legal_data_service
from app.services.operations import service as operations_service
from app.services.research import importer as research_importer
from app.services.search_index import service as index_service
from app.services.system_health import service as system_health_service
from app.models.system_health import BackupTrigger, HealthTrigger
from app.services.security.context import ActorContext, reset_current_actor, set_current_actor


async def actor_for_job(db: AsyncSession, job: BackgroundJob) -> ActorContext:
    if not job.requested_by_membership_id:
        raise RuntimeError("Job requires an initiating membership")
    membership = await db.get(OrganizationMembership, job.requested_by_membership_id)
    if not membership or membership.status != MembershipStatus.ACTIVE:
        raise RuntimeError("Initiating membership is no longer active")
    if membership.organization_id != job.organization_id:
        raise RuntimeError("Initiating membership no longer matches the job organization")
    user = await db.get(SecurityUser, membership.user_id)
    if not user:
        raise RuntimeError("Initiating user no longer exists")
    return ActorContext(
        user_id=user.id, membership_id=membership.id, organization_id=membership.organization_id,
        email=user.email, display_name=user.display_name, role=membership.role,
        mfa_enrolled=user.mfa_enrolled, session_id=None,
    )


async def execute_handler(db: AsyncSession, job: BackgroundJob) -> dict:
    actor = await actor_for_job(db, job)
    token = set_current_actor(actor)
    p = job.payload_json or {}
    try:
        return await _execute_handler_inner(db, job, actor, p)
    finally:
        reset_current_actor(token)


async def _execute_handler_inner(db: AsyncSession, job: BackgroundJob, actor: ActorContext, p: dict) -> dict:
    if job.kind in {JobKind.SEARCH_ORG_REBUILD,JobKind.SEARCH_DUPLICATE_SCAN,JobKind.ANALYTICS_SNAPSHOT,JobKind.ANALYTICS_RISK_REBUILD,JobKind.OPERATIONS_DUE_SWEEP,JobKind.CORPUS_RESOLVE_CITATIONS,JobKind.LEGAL_DATA_FEED_SYNC,JobKind.LEGAL_DATA_INTEGRITY_SWEEP,JobKind.SYSTEM_HEALTH_CHECK,JobKind.BACKUP_RUN,JobKind.RESTORE_VERIFY} and actor.role.value not in {"owner","admin","partner"}:
        raise RuntimeError("Initiating membership no longer has permission for this maintenance job")
    if job.kind == JobKind.DOCUMENT_REPROCESS:
        row = await document_service.process_document(db, UUID(str(p["document_id"])), allow_ocr=bool(p.get("allow_ocr", True)), rebuild_intelligence=False, reindex_search=False)
        return {"document_id": str(row.id), "status": row.processing_status.value}
    if job.kind == JobKind.SEARCH_DOCUMENT_REINDEX:
        return await index_service.reindex_document(db, UUID(str(p["document_id"])))
    if job.kind == JobKind.SEARCH_ORG_REBUILD:
        row = await index_service.rebuild_organization_index(db, actor, include_corpus=bool(p.get("include_corpus", True)))
        return {"search_index_job_id": str(row.id), "entries_seen": row.entries_seen, "entries_created": row.entries_created, "entries_updated": row.entries_updated}
    if job.kind == JobKind.SEARCH_DUPLICATE_SCAN:
        return {"created": await index_service.detect_duplicates(db, actor, limit=int(p.get("limit", 10000)))}
    if job.kind == JobKind.MATTER_INTELLIGENCE_REBUILD:
        return await rebuild_matter_intelligence(db, UUID(str(p["matter_id"])))
    if job.kind == JobKind.EVIDENCE_MATTER_REBUILD:
        return await evidence_service.rebuild_matter(db, actor, UUID(str(p["matter_id"])))
    if job.kind == JobKind.ANALYTICS_SNAPSHOT:
        row = await analytics_service.create_snapshot(db, actor, kind=SnapshotKind.MANUAL, notes=str(p.get("notes") or "Background snapshot"))
        return {"snapshot_id": str(row.id), "payload_hash": row.payload_hash}
    if job.kind == JobKind.ANALYTICS_RISK_REBUILD:
        return await analytics_service.rebuild_risk_signals(db, actor)
    if job.kind == JobKind.OPERATIONS_DUE_SWEEP:
        return await operations_service.run_due_sweep(db, actor, SweepRequest(horizon_hours=int(p.get("horizon_hours",48)), escalate_overdue_hours=int(p.get("escalate_overdue_hours",24))))
    if job.kind == JobKind.CORPUS_RESOLVE_CITATIONS:
        jid = UUID(str(p["judgment_id"])) if p.get("judgment_id") else None
        return await research_importer.resolve_citations(db, judgment_id=jid)
    if job.kind == JobKind.LEGAL_DATA_FEED_SYNC:
        return await legal_data_service.sync_feed(db, actor, UUID(str(p["feed_id"])))
    if job.kind == JobKind.LEGAL_DATA_INTEGRITY_SWEEP:
        return await legal_data_service.integrity_sweep(db, actor)
    if job.kind == JobKind.SYSTEM_HEALTH_CHECK:
        detail = await system_health_service.run_health_checks(db, actor, trigger=HealthTrigger.WORKER)
        status = detail["run"].status
        return {"health_run_id": str(detail["run"].id), "status": getattr(status, "value", str(status))}
    if job.kind == JobKind.BACKUP_RUN:
        return await system_health_service.execute_backup(db, actor, UUID(str(p["policy_id"])), trigger=BackupTrigger.WORKER)
    if job.kind == JobKind.RESTORE_VERIFY:
        return await system_health_service.execute_restore_verification(db, actor, UUID(str(p["backup_run_id"])))
    if job.kind == JobKind.EVIDENCE_BUNDLE_BUILD:
        payload=BundleCreate(title=str(p.get("title") or "Litigation bundle"),bundle_type=str(p.get("bundle_type") or "hearing"),description=p.get("description"),evidence_item_ids=[UUID(str(v)) for v in p.get("evidence_item_ids",[])],issue_ids=[UUID(str(v)) for v in p.get("issue_ids",[])])
        row=await evidence_service.create_bundle(db,actor,UUID(str(p["matter_id"])),payload)
        return {"bundle_id":str(row.id),"status":row.status.value,"sha256":row.sha256,"storage_key":row.storage_key}
    if job.kind == JobKind.EVIDENCE_BUNDLE_FINALIZE:
        row = await evidence_service.finalize_bundle(db, actor, UUID(str(p["bundle_id"])))
        return {"bundle_id": str(row.id), "status": row.status.value, "sha256": row.sha256}
    raise RuntimeError(f"No handler registered for {job.kind}")
