from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import zipfile
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.url import prepare_database_url
from app.services.documents.storage import backup_object_storage_to_zip, check_storage_health
from app.models.jobs import BackgroundJob, BackgroundWorker, JobStatus
from app.models.operations import CourtCaseTracker, CourtTrackerStatus
from app.models.search_index import SearchIndexHealthSnapshot
from app.models.security import AuditOutcome, OrganizationRole
from app.models.system_health import (
    BackupArtifact,
    BackupArtifactKind,
    BackupPolicy,
    BackupRun,
    BackupStatus,
    BackupTrigger,
    HealthStatus,
    HealthTrigger,
    IncidentStatus,
    RecoveryObjective,
    RestoreDrill,
    RestoreDrillStatus,
    SystemHealthComponent,
    SystemHealthRun,
    SystemIncident,
    SystemIncidentEvent,
    SystemMetricSnapshot,
)
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext
from app.services.system_health.engine import (
    age_seconds,
    aware,
    canonical_hash,
    incident_fingerprint,
    incident_severity,
    overall_status,
    restore_verification_status,
    retention_keep_ids,
    rpo_status,
    safe_filename,
    sha256_file,
    storage_free_percent,
    utcnow,
)

MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}
ACTIVE_JOB_STATUSES = {JobStatus.QUEUED, JobStatus.LEASED, JobStatus.RUNNING, JobStatus.RETRY_WAIT}


def _require_manager(actor: ActorContext) -> None:
    if actor.role not in MANAGER_ROLES:
        raise HTTPException(403, "Partner, admin or owner role required")


async def _audit(db: AsyncSession, actor: ActorContext, action: str, resource_type: str, resource_id: UUID | str | None, metadata: dict | None = None) -> None:
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        outcome=AuditOutcome.SUCCESS,
        metadata=metadata or {},
    )


async def get_or_create_objectives(db: AsyncSession, actor: ActorContext) -> RecoveryObjective:
    row = await db.scalar(select(RecoveryObjective).where(RecoveryObjective.organization_id == actor.organization_id))
    if row is None:
        row = RecoveryObjective(
            organization_id=actor.organization_id,
            updated_by_membership_id=actor.membership_id,
            restore_verification_days=settings.system_health_default_restore_verification_days,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def update_objectives(db: AsyncSession, actor: ActorContext, values: dict) -> RecoveryObjective:
    _require_manager(actor)
    row = await get_or_create_objectives(db, actor)
    for key, value in values.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    row.updated_by_membership_id = actor.membership_id
    await _audit(db, actor, "system.recovery_objectives.update", "recovery_objective", row.id, values)
    await db.commit()
    await db.refresh(row)
    return row


def _component(key: str, category: str, status: HealthStatus, message_en: str, message_hi: str | None = None, *, latency_ms: int | None = None, metrics: dict | None = None) -> dict:
    return {
        "component_key": key,
        "category": category,
        "status": status,
        "message_en": message_en,
        "message_hi": message_hi,
        "latency_ms": latency_ms,
        "metrics_json": metrics or {},
    }


async def _database_health(db: AsyncSession, objectives: RecoveryObjective) -> dict:
    started = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        latency = max(0, round((time.perf_counter() - started) * 1000))
        status = HealthStatus.HEALTHY if latency <= objectives.max_database_latency_ms else HealthStatus.DEGRADED
        return _component(
            "database", "core", status,
            f"Database responded in {latency} ms.",
            f"डेटाबेस ने {latency} मिलीसेकंड में उत्तर दिया।",
            latency_ms=latency,
            metrics={"latency_ms": latency, "threshold_ms": objectives.max_database_latency_ms},
        )
    except Exception as exc:
        return _component("database", "core", HealthStatus.DOWN, f"Database health query failed: {str(exc)[:300]}", "डेटाबेस स्वास्थ्य जाँच विफल हुई।")


def _storage_health(objectives: RecoveryObjective) -> dict:
    # Production source documents may live in S3-compatible object storage while generated
    # artifacts/cache still use local/shared disk. Verify both boundaries.
    root = (settings.storage_cache_root if settings.storage_backend.casefold() == "s3" else settings.storage_root).resolve()
    try:
        object_health = check_storage_health()
        if not object_health.get("ready"):
            return _component("storage", "core", HealthStatus.DOWN, f"Object/local storage probe failed: {object_health.get('error','unavailable')}", "स्टोरेज स्वास्थ्य जाँच विफल हुई।", metrics=object_health)
        root.mkdir(parents=True, exist_ok=True)
        probe = root / f".health-{os.getpid()}-{int(time.time() * 1000)}"
        probe.write_text("junior-lawyer-health", encoding="utf-8")
        if probe.read_text(encoding="utf-8") != "junior-lawyer-health":
            raise OSError("storage cache probe read-back mismatch")
        probe.unlink(missing_ok=True)
        disk = shutil.disk_usage(root)
        free_pct = storage_free_percent(disk.total, disk.free)
        status = HealthStatus.HEALTHY if free_pct >= objectives.min_storage_free_percent else HealthStatus.DEGRADED
        metrics={"path": str(root), "backend": settings.storage_backend, "free_bytes": disk.free, "total_bytes": disk.total, "free_percent": free_pct, "threshold_percent": objectives.min_storage_free_percent, **object_health}
        return _component("storage", "core", status, f"Storage backend is reachable; local cache has {free_pct:.1f}% free.", f"स्टोरेज उपलब्ध है; स्थानीय कैश में {free_pct:.1f}% स्थान खाली है।", metrics=metrics)
    except Exception as exc:
        return _component("storage", "core", HealthStatus.DOWN, f"Storage probe failed: {str(exc)[:300]}", "स्टोरेज स्वास्थ्य जाँच विफल हुई।", metrics={"path": str(root), "backend": settings.storage_backend})


async def _jobs_health(db: AsyncSession, actor: ActorContext, objectives: RecoveryObjective) -> tuple[dict, dict]:
    now = utcnow()
    active_stmt = select(BackgroundJob).where(BackgroundJob.organization_id == actor.organization_id, BackgroundJob.status.in_(list(ACTIVE_JOB_STATUSES)))
    active = list((await db.scalars(active_stmt)).all())
    dead = int(await db.scalar(select(func.count(BackgroundJob.id)).where(BackgroundJob.organization_id == actor.organization_id, BackgroundJob.status == JobStatus.DEAD_LETTER)) or 0)
    oldest_age = 0
    slow = 0
    for job in active:
        reference = job.started_at or job.scheduled_at or job.created_at
        age = age_seconds(now, reference) or 0
        oldest_age = max(oldest_age, age)
        if job.status in {JobStatus.RUNNING, JobStatus.LEASED} and age >= objectives.slow_job_seconds:
            slow += 1
    workers = list((await db.scalars(select(BackgroundWorker).where(BackgroundWorker.organization_id == actor.organization_id))).all())
    online = 0
    stale = 0
    for worker in workers:
        age = age_seconds(now, worker.heartbeat_at)
        if age is not None and age <= objectives.worker_stale_seconds:
            online += 1
        else:
            stale += 1
    if active and online == 0:
        worker_status = HealthStatus.DOWN
        worker_message = f"{len(active)} active jobs are waiting but no worker heartbeat is current."
    elif stale:
        worker_status = HealthStatus.DEGRADED
        worker_message = f"{online} workers online; {stale} worker heartbeats are stale."
    else:
        worker_status = HealthStatus.HEALTHY
        worker_message = f"{online} workers online; {len(active)} active jobs."
    queue_status = HealthStatus.HEALTHY
    if oldest_age > objectives.max_queue_lag_seconds * 2 or dead > 0:
        queue_status = HealthStatus.DOWN if dead > 0 and active else HealthStatus.DEGRADED
    elif oldest_age > objectives.max_queue_lag_seconds or slow > 0:
        queue_status = HealthStatus.DEGRADED
    return (
        _component("workers", "processing", worker_status, worker_message, "बैकग्राउंड वर्कर स्वास्थ्य जाँचा गया।", metrics={"online": online, "stale": stale, "active_jobs": len(active), "stale_after_seconds": objectives.worker_stale_seconds}),
        _component("queues", "processing", queue_status, f"Oldest active job age: {oldest_age}s; dead-letter: {dead}; slow jobs: {slow}.", "क्यू लैग और विफल जॉब जाँचे गए।", metrics={"oldest_age_seconds": oldest_age, "dead_letter_count": dead, "slow_job_count": slow, "lag_threshold_seconds": objectives.max_queue_lag_seconds}),
    )


async def _search_health(db: AsyncSession, actor: ActorContext) -> dict:
    now = utcnow()
    snapshot = await db.scalar(select(SearchIndexHealthSnapshot).where(SearchIndexHealthSnapshot.organization_id == actor.organization_id).order_by(SearchIndexHealthSnapshot.created_at.desc()).limit(1))
    if snapshot is None:
        return _component("search_index", "search", HealthStatus.DEGRADED, "No search-index health snapshot has been recorded yet.", "अभी तक सर्च इंडेक्स हेल्थ स्नैपशॉट दर्ज नहीं हुआ है।", metrics={"age_seconds": None})
    age = age_seconds(now, snapshot.created_at) or 0
    status = HealthStatus.HEALTHY if age <= 86400 and snapshot.stale_count == 0 else HealthStatus.DEGRADED
    return _component("search_index", "search", status, f"Search index has {snapshot.entry_count} entries; snapshot age {age}s; stale entries {snapshot.stale_count}.", "सर्च इंडेक्स की स्थिति जाँची गई।", metrics={"age_seconds": age, "entry_count": snapshot.entry_count, "stale_count": snapshot.stale_count, "last_completed_job_at": str(snapshot.last_completed_job_at) if snapshot.last_completed_job_at else None})


def _ocr_health() -> dict:
    path = shutil.which("tesseract")
    if not settings.ocr_enabled:
        return _component("ocr", "documents", HealthStatus.HEALTHY, "OCR is disabled by configuration.", "OCR कॉन्फ़िगरेशन द्वारा बंद है।", metrics={"enabled": False})
    if path:
        return _component("ocr", "documents", HealthStatus.HEALTHY, "Tesseract is available for local English/Hindi OCR.", "स्थानीय अंग्रेज़ी/हिन्दी OCR के लिए Tesseract उपलब्ध है।", metrics={"enabled": True, "executable": path, "languages": settings.ocr_languages})
    return _component("ocr", "documents", HealthStatus.DEGRADED, "OCR is enabled but the Tesseract executable is unavailable.", "OCR चालू है लेकिन Tesseract उपलब्ध नहीं है।", metrics={"enabled": True, "languages": settings.ocr_languages})


def _ai_health() -> dict:
    local = bool(settings.ai_enabled and settings.ai_local_enabled and settings.ai_local_base_url)
    remote = bool(settings.ai_enabled and settings.ai_remote_enabled and settings.ai_remote_base_url and settings.ai_remote_model)
    if not settings.ai_enabled:
        return _component("ai_providers", "ai", HealthStatus.HEALTHY, "Generative AI is disabled; deterministic workflows remain available.", "जनरेटिव AI बंद है; deterministic workflows उपलब्ध हैं।", metrics={"ai_enabled": False, "local_configured": False, "remote_configured": False})
    status = HealthStatus.HEALTHY if local or remote else HealthStatus.DEGRADED
    return _component("ai_providers", "ai", status, f"AI enabled. Local configured: {local}; remote configured: {remote}. No paid/network probe was sent.", "AI कॉन्फ़िगरेशन जाँचा गया; कोई paid/network probe नहीं भेजा गया।", metrics={"ai_enabled": True, "local_configured": local, "remote_configured": remote, "network_probe": False})


async def _court_health(db: AsyncSession, actor: ActorContext) -> dict:
    rows = list((await db.scalars(select(CourtCaseTracker).where(CourtCaseTracker.organization_id == actor.organization_id, CourtCaseTracker.status == CourtTrackerStatus.ACTIVE))).all())
    if not rows:
        return _component("court_connectors", "court", HealthStatus.HEALTHY, "No active court trackers require connector health.", "कोई सक्रिय कोर्ट ट्रैकर नहीं है।", metrics={"active_trackers": 0})
    now = utcnow()
    stale = sum(1 for row in rows if row.last_checked_at is None or (age_seconds(now, row.last_checked_at) or 0) > 172800)
    status = HealthStatus.DEGRADED if stale else HealthStatus.HEALTHY
    return _component("court_connectors", "court", status, f"{len(rows)} active court trackers; {stale} have not been refreshed within 48 hours. No CAPTCHA bypass is attempted.", "सक्रिय कोर्ट ट्रैकर की ताज़गी जाँची गई; CAPTCHA bypass नहीं किया जाता।", metrics={"active_trackers": len(rows), "stale_trackers": stale, "automated_captcha_bypass": False})


async def _backup_health(db: AsyncSession, actor: ActorContext, objectives: RecoveryObjective) -> tuple[dict, dict]:
    now = utcnow()
    last = await db.scalar(select(BackupRun).where(BackupRun.organization_id == actor.organization_id, BackupRun.status.in_([BackupStatus.SUCCEEDED, BackupStatus.VERIFIED])).order_by(BackupRun.finished_at.desc()).limit(1))
    rpo_state, backup_age = rpo_status(last_backup_at=last.finished_at if last else None, now=now, target_minutes=objectives.target_rpo_minutes)
    backup_message = "No successful backup has been recorded." if backup_age is None else f"Latest successful backup is {backup_age // 60} minutes old; target RPO is {objectives.target_rpo_minutes} minutes."
    drill = await db.scalar(select(RestoreDrill).where(RestoreDrill.organization_id == actor.organization_id, RestoreDrill.status.in_([RestoreDrillStatus.PASSED, RestoreDrillStatus.REVIEWED])).order_by(RestoreDrill.finished_at.desc()).limit(1))
    restore_state, drill_age = restore_verification_status(last_verified_at=drill.finished_at if drill else None, now=now, target_days=objectives.restore_verification_days)
    restore_message = "No successful restore verification has been recorded." if drill_age is None else f"Latest restore verification is {drill_age // 86400} days old; target is {objectives.restore_verification_days} days."
    return (
        _component("backups", "recovery", rpo_state, backup_message, "बैकअप RPO स्थिति जाँची गई।", metrics={"age_seconds": backup_age, "target_rpo_minutes": objectives.target_rpo_minutes, "last_backup_id": str(last.id) if last else None}),
        _component("restore_verification", "recovery", restore_state, restore_message, "रीस्टोर verification की ताज़गी जाँची गई।", metrics={"age_seconds": drill_age, "target_days": objectives.restore_verification_days, "last_drill_id": str(drill.id) if drill else None}),
    )


async def _sync_incidents(db: AsyncSession, actor: ActorContext, components: list[dict], now) -> None:
    for component in components:
        fingerprint = incident_fingerprint(component["component_key"])
        incident = await db.scalar(select(SystemIncident).where(SystemIncident.organization_id == actor.organization_id, SystemIncident.fingerprint == fingerprint))
        status = component["status"]
        if status in {HealthStatus.DOWN, HealthStatus.DEGRADED}:
            severity = incident_severity(component["component_key"], status)
            if incident is None:
                incident = SystemIncident(
                    organization_id=actor.organization_id,
                    component_key=component["component_key"],
                    fingerprint=fingerprint,
                    severity=severity,
                    status=IncidentStatus.OPEN,
                    title=f"{component['component_key'].replace('_', ' ').title()} health issue",
                    description=component["message_en"],
                    first_seen_at=now,
                    last_seen_at=now,
                    metadata_json={"health_status": str(status)},
                )
                db.add(incident)
                await db.flush()
                db.add(SystemIncidentEvent(incident_id=incident.id, event_type="opened", message=component["message_en"], metadata_json=component.get("metrics_json", {})))
            else:
                incident.last_seen_at = now
                incident.severity = severity
                incident.description = component["message_en"]
                incident.metadata_json = {**(incident.metadata_json or {}), "health_status": str(status)}
                if incident.status == IncidentStatus.RESOLVED:
                    incident.status = IncidentStatus.OPEN
                    incident.resolved_at = None
                    incident.resolved_by_membership_id = None
                    db.add(SystemIncidentEvent(incident_id=incident.id, event_type="reopened", message=component["message_en"], metadata_json=component.get("metrics_json", {})))
        elif incident is not None and incident.status != IncidentStatus.RESOLVED:
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = now
            db.add(SystemIncidentEvent(incident_id=incident.id, event_type="auto_resolved", message="Component returned to healthy state."))


async def run_health_checks(db: AsyncSession, actor: ActorContext, *, trigger: HealthTrigger = HealthTrigger.MANUAL) -> dict:
    _require_manager(actor)
    objectives = await get_or_create_objectives(db, actor)
    now = utcnow()
    run = SystemHealthRun(organization_id=actor.organization_id, requested_by_membership_id=actor.membership_id, trigger=trigger, status=HealthStatus.UNKNOWN, started_at=now, summary_json={})
    db.add(run)
    await db.flush()

    components = [await _database_health(db, objectives), _storage_health(objectives)]
    workers, queues = await _jobs_health(db, actor, objectives)
    components.extend([workers, queues, await _search_health(db, actor), _ocr_health(), _ai_health(), await _court_health(db, actor)])
    backup, restore = await _backup_health(db, actor, objectives)
    components.extend([backup, restore])

    checked_at = utcnow()
    for item in components:
        db.add(SystemHealthComponent(run_id=run.id, checked_at=checked_at, **item))

    run.status = overall_status([item["status"] for item in components])
    run.finished_at = checked_at
    counts = {status.value: sum(1 for item in components if item["status"] == status) for status in HealthStatus}
    run.summary_json = {"component_count": len(components), "counts": counts, "hostname": socket.gethostname()}
    run.snapshot_hash = canonical_hash({"status": run.status.value, "components": [{"key": i["component_key"], "status": i["status"].value, "metrics": i["metrics_json"]} for i in components]})

    await _sync_incidents(db, actor, components, checked_at)

    storage_metrics = next(item["metrics_json"] for item in components if item["component_key"] == "storage")
    queue_metrics = queues["metrics_json"]
    worker_metrics = workers["metrics_json"]
    search_metrics = next(item["metrics_json"] for item in components if item["component_key"] == "search_index")
    ai_metrics = next(item["metrics_json"] for item in components if item["component_key"] == "ai_providers")
    db_component = next(item for item in components if item["component_key"] == "database")
    ocr_component = next(item for item in components if item["component_key"] == "ocr")
    metric_payload = {
        "overall_status": run.status.value,
        "database_latency_ms": db_component["latency_ms"],
        "storage_free_bytes": storage_metrics.get("free_bytes"),
        "storage_total_bytes": storage_metrics.get("total_bytes"),
        "queue_oldest_age_seconds": queue_metrics.get("oldest_age_seconds", 0),
        "dead_letter_count": queue_metrics.get("dead_letter_count", 0),
        "slow_job_count": queue_metrics.get("slow_job_count", 0),
        "online_worker_count": worker_metrics.get("online", 0),
        "stale_worker_count": worker_metrics.get("stale", 0),
        "search_index_age_seconds": search_metrics.get("age_seconds"),
        "tesseract_available": bool(ocr_component["metrics_json"].get("executable")),
        "local_ai_configured": bool(ai_metrics.get("local_configured")),
        "remote_ai_configured": bool(ai_metrics.get("remote_configured")),
    }
    snapshot_hash = canonical_hash(metric_payload)
    db.add(SystemMetricSnapshot(organization_id=actor.organization_id, captured_at=checked_at, snapshot_hash=snapshot_hash, metrics_json={"components": run.summary_json}, **metric_payload))
    await _audit(db, actor, "system.health.check", "system_health_run", run.id, {"status": run.status.value, "snapshot_hash": run.snapshot_hash})
    await db.commit()
    return await health_run_detail(db, actor, run.id)


async def health_run_detail(db: AsyncSession, actor: ActorContext, run_id: UUID) -> dict:
    _require_manager(actor)
    run = await db.get(SystemHealthRun, run_id)
    if not run or run.organization_id != actor.organization_id:
        raise HTTPException(404, "Health run not found")
    components = list((await db.scalars(select(SystemHealthComponent).where(SystemHealthComponent.run_id == run.id).order_by(SystemHealthComponent.category, SystemHealthComponent.component_key))).all())
    return {"run": run, "components": components}


async def list_incidents(db: AsyncSession, actor: ActorContext, *, include_resolved: bool = False, limit: int = 100) -> list[SystemIncident]:
    _require_manager(actor)
    stmt = select(SystemIncident).where(SystemIncident.organization_id == actor.organization_id)
    if not include_resolved:
        stmt = stmt.where(SystemIncident.status != IncidentStatus.RESOLVED)
    return list((await db.scalars(stmt.order_by(SystemIncident.last_seen_at.desc()).limit(limit))).all())


async def update_incident(db: AsyncSession, actor: ActorContext, incident_id: UUID, *, action: str, note: str | None = None) -> SystemIncident:
    _require_manager(actor)
    row = await db.get(SystemIncident, incident_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Incident not found")
    now = utcnow()
    if action == "acknowledge":
        row.status = IncidentStatus.ACKNOWLEDGED
        row.acknowledged_by_membership_id = actor.membership_id
        row.acknowledged_at = now
    elif action == "resolve":
        row.status = IncidentStatus.RESOLVED
        row.resolved_by_membership_id = actor.membership_id
        row.resolved_at = now
    elif action == "reopen":
        row.status = IncidentStatus.OPEN
        row.resolved_by_membership_id = None
        row.resolved_at = None
    else:
        raise HTTPException(422, "Unknown incident action")
    db.add(SystemIncidentEvent(incident_id=row.id, membership_id=actor.membership_id, event_type=action, message=note or action.replace("_", " ").title()))
    await _audit(db, actor, f"system.incident.{action}", "system_incident", row.id, {"note": note})
    await db.commit()
    await db.refresh(row)
    return row


async def create_default_backup_policy(db: AsyncSession, actor: ActorContext) -> BackupPolicy:
    _require_manager(actor)
    existing = await db.scalar(select(BackupPolicy).where(BackupPolicy.organization_id == actor.organization_id).order_by(BackupPolicy.created_at).limit(1))
    if existing:
        return existing
    row = BackupPolicy(
        organization_id=actor.organization_id,
        name="Daily local recovery copy",
        enabled=True,
        include_database=True,
        include_documents=True,
        schedule_rrule="FREQ=DAILY;INTERVAL=1",
        retention_days=30,
        max_backups=30,
        destination_kind="local",
        encryption_mode="none",
        rpo_minutes=1440,
        rto_minutes=240,
        metadata_json={"review_required": True, "production_note": "Use encrypted off-site storage for production."},
    )
    db.add(row)
    await _audit(db, actor, "system.backup_policy.create_default", "backup_policy", row.id)
    await db.commit()
    await db.refresh(row)
    return row


async def create_backup_policy(db: AsyncSession, actor: ActorContext, values: dict) -> BackupPolicy:
    _require_manager(actor)
    if not values.get("include_database", True) and not values.get("include_documents", True):
        raise HTTPException(422, "A backup policy must include the database, documents, or both")
    row = BackupPolicy(organization_id=actor.organization_id, **values)
    db.add(row)
    await db.flush()
    await _audit(db, actor, "system.backup_policy.create", "backup_policy", row.id)
    await db.commit(); await db.refresh(row); return row


async def update_backup_policy(db: AsyncSession, actor: ActorContext, policy_id: UUID, values: dict) -> BackupPolicy:
    _require_manager(actor)
    row = await db.get(BackupPolicy, policy_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Backup policy not found")
    for key, value in values.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    if not row.include_database and not row.include_documents:
        raise HTTPException(422, "A backup policy must include the database, documents, or both")
    await _audit(db, actor, "system.backup_policy.update", "backup_policy", row.id, values)
    await db.commit(); await db.refresh(row); return row


async def list_backup_policies(db: AsyncSession, actor: ActorContext) -> list[BackupPolicy]:
    _require_manager(actor)
    return list((await db.scalars(select(BackupPolicy).where(BackupPolicy.organization_id == actor.organization_id).order_by(BackupPolicy.created_at))).all())


def _local_destination(policy: BackupPolicy, run: BackupRun) -> Path:
    if policy.destination_kind != "local":
        raise RuntimeError("External backup destination requires a configured connector")
    if policy.encryption_mode != "none":
        raise RuntimeError("External encryption mode requires a configured encrypted-storage connector")
    root = settings.backup_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    relative = Path(policy.destination_path or safe_filename(policy.name))
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("Backup destination_path must be a safe relative path below BACKUP_ROOT")
    destination = (root / str(policy.organization_id) / relative / str(run.id)).resolve()
    allowed = (root / str(policy.organization_id)).resolve()
    try:
        destination.relative_to(allowed)
    except ValueError as exc:
        raise RuntimeError("Backup destination escapes organization backup root") from exc
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _sqlite_source_path() -> Path:
    url = make_url(prepare_database_url(settings.database_url).url)
    database = url.database
    if not database or database == ":memory:":
        raise RuntimeError("In-memory SQLite cannot be backed up as a durable artifact")
    path = Path(database)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def _backup_sqlite(target: Path) -> None:
    source = _sqlite_source_path()
    if not source.exists():
        raise RuntimeError(f"SQLite database file does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()


def _postgres_pg_dump(target: Path) -> None:
    executable = shutil.which("pg_dump")
    if not executable:
        raise RuntimeError("pg_dump is required for PostgreSQL backups but is not installed")
    url = make_url(prepare_database_url(settings.database_url).url)
    if not url.database:
        raise RuntimeError("PostgreSQL database name is missing")
    cmd = [executable, "--format=custom", "--file", str(target)]
    if url.host: cmd.extend(["--host", url.host])
    if url.port: cmd.extend(["--port", str(url.port)])
    if url.username: cmd.extend(["--username", url.username])
    cmd.append(url.database)
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr[-500:]}")


def _backup_database(target_dir: Path) -> Path:
    if prepare_database_url(settings.database_url).is_sqlite:
        target = target_dir / "database.sqlite3"
        _backup_sqlite(target)
        return target
    if prepare_database_url(settings.database_url).url.startswith("postgresql"):
        target = target_dir / "database.pg_dump"
        _postgres_pg_dump(target)
        return target
    raise RuntimeError("Database backup adapter is not implemented for this database dialect")


def _storage_sources() -> list[Path]:
    candidates = [settings.storage_root, settings.storage_root.parent / "legal_drafts", settings.storage_root.parent / "contracts"]
    seen: set[Path] = set(); result: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved not in seen:
            seen.add(resolved); result.append(resolved)
    return result


def _backup_documents(target_dir: Path) -> tuple[Path, int]:
    target = target_dir / "application-files.zip"
    count = 0
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        # Batch 24: when source documents use S3-compatible storage, stream those objects
        # directly into the backup instead of silently backing up only local generated files.
        count += backup_object_storage_to_zip(archive)
        for source_root in _storage_sources():
            prefix = source_root.name
            for path in sorted(source_root.rglob("*")):
                if not path.is_file() or path.is_symlink():
                    continue
                if ".staging" in path.parts or ".health-" in path.name:
                    continue
                relative = path.relative_to(source_root)
                archive.write(path, arcname=str(Path(prefix) / relative))
                count += 1
    return target, count


async def _add_artifact(db: AsyncSession, run: BackupRun, kind: BackupArtifactKind, path: Path, metadata: dict | None = None) -> BackupArtifact:
    row = BackupArtifact(backup_run_id=run.id, kind=kind, storage_path=str(path.resolve()), filename=path.name, size_bytes=path.stat().st_size, sha256=sha256_file(path), encrypted=False, metadata_json=metadata or {})
    db.add(row); await db.flush(); return row


async def execute_backup(db: AsyncSession, actor: ActorContext, policy_id: UUID, *, trigger: BackupTrigger = BackupTrigger.WORKER) -> dict:
    _require_manager(actor)
    policy = await db.get(BackupPolicy, policy_id)
    if not policy or policy.organization_id != actor.organization_id:
        raise HTTPException(404, "Backup policy not found")
    if not policy.enabled:
        raise HTTPException(409, "Backup policy is disabled")
    run = BackupRun(organization_id=actor.organization_id, policy_id=policy.id, requested_by_membership_id=actor.membership_id, trigger=trigger, status=BackupStatus.RUNNING, started_at=utcnow(), metadata_json={"hostname": socket.gethostname()})
    db.add(run); await db.commit(); await db.refresh(run)
    try:
        destination = await asyncio.to_thread(_local_destination, policy, run)
        artifacts: list[BackupArtifact] = []
        document_count = 0
        if policy.include_database:
            db_path = await asyncio.to_thread(_backup_database, destination)
            artifacts.append(await _add_artifact(db, run, BackupArtifactKind.DATABASE, db_path, {"database_dialect": make_url(prepare_database_url(settings.database_url).url).get_backend_name()}))
            run.database_status = "succeeded"
        else:
            run.database_status = "not_included"
        if policy.include_documents:
            documents_path, document_count = await asyncio.to_thread(_backup_documents, destination)
            artifacts.append(await _add_artifact(db, run, BackupArtifactKind.DOCUMENTS, documents_path, {"file_count": document_count}))
            run.documents_status = "succeeded"
        else:
            run.documents_status = "not_included"
        manifest_payload = {
            "backup_run_id": str(run.id),
            "organization_id": str(actor.organization_id),
            "created_at": utcnow().isoformat(),
            "artifacts": [{"kind": str(a.kind), "filename": a.filename, "size_bytes": a.size_bytes, "sha256": a.sha256} for a in artifacts],
            "document_count": document_count,
        }
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        manifest = await _add_artifact(db, run, BackupArtifactKind.MANIFEST, manifest_path, {"document_count": document_count})
        artifacts.append(manifest)
        run.total_bytes = sum(item.size_bytes for item in artifacts)
        run.manifest_sha256 = manifest.sha256
        run.status = BackupStatus.SUCCEEDED
        run.finished_at = utcnow()
        policy.last_run_at = run.finished_at
        await _audit(db, actor, "system.backup.succeeded", "backup_run", run.id, {"policy_id": str(policy.id), "total_bytes": run.total_bytes, "manifest_sha256": run.manifest_sha256})
        await db.commit()
        await apply_backup_retention(db, actor, policy)
        return {"backup_run_id": str(run.id), "status": run.status.value, "total_bytes": run.total_bytes, "manifest_sha256": run.manifest_sha256}
    except Exception as exc:
        await db.rollback()
        run = await db.get(BackupRun, run.id)
        run.status = BackupStatus.FAILED
        run.error = str(exc)[:4000]
        run.finished_at = utcnow()
        await _audit(db, actor, "system.backup.failed", "backup_run", run.id, {"policy_id": str(policy.id), "error_type": type(exc).__name__})
        await db.commit()
        raise


async def apply_backup_retention(db: AsyncSession, actor: ActorContext, policy: BackupPolicy) -> dict:
    _require_manager(actor)
    rows = list((await db.scalars(select(BackupRun).where(BackupRun.organization_id == actor.organization_id, BackupRun.policy_id == policy.id, BackupRun.status.in_([BackupStatus.SUCCEEDED, BackupStatus.VERIFIED])).order_by(BackupRun.created_at.desc()))).all())
    keep = retention_keep_ids([(str(row.id), row.created_at) for row in rows], now=utcnow(), retention_days=policy.retention_days, max_backups=policy.max_backups)
    deleted = 0
    root = settings.backup_root.resolve()
    for row in rows:
        if str(row.id) in keep:
            continue
        artifacts = list((await db.scalars(select(BackupArtifact).where(BackupArtifact.backup_run_id == row.id))).all())
        for artifact in artifacts:
            path = Path(artifact.storage_path).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
        await db.delete(row)
        deleted += 1
    if deleted:
        await db.commit()
    return {"deleted_backup_runs": deleted}


async def list_backup_runs(db: AsyncSession, actor: ActorContext, limit: int = 30) -> list[BackupRun]:
    _require_manager(actor)
    return list((await db.scalars(select(BackupRun).where(BackupRun.organization_id == actor.organization_id).order_by(BackupRun.created_at.desc()).limit(limit))).all())


async def backup_run_detail(db: AsyncSession, actor: ActorContext, run_id: UUID) -> dict:
    _require_manager(actor)
    run = await db.get(BackupRun, run_id)
    if not run or run.organization_id != actor.organization_id:
        raise HTTPException(404, "Backup run not found")
    artifacts = list((await db.scalars(select(BackupArtifact).where(BackupArtifact.backup_run_id == run.id).order_by(BackupArtifact.created_at))).all())
    return {"run": run, "artifacts": artifacts}


def _verify_database_artifact(path: Path) -> tuple[bool, dict]:
    if path.suffix in {".sqlite3", ".db", ".sqlite"}:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA quick_check").fetchone()
            ok = bool(result and str(result[0]).casefold() == "ok")
            count = connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            return ok, {"quick_check": result[0] if result else None, "table_count": int(count)}
        finally:
            connection.close()
    if path.suffix == ".pg_dump":
        executable = shutil.which("pg_restore")
        if not executable:
            return False, {"error": "pg_restore is unavailable for verification"}
        result = subprocess.run([executable, "--list", str(path)], capture_output=True, text=True, timeout=600)
        return result.returncode == 0, {"list_lines": len(result.stdout.splitlines()), "stderr": result.stderr[-300:]}
    return False, {"error": "Unknown database artifact format"}


def _verify_documents_artifact(path: Path) -> tuple[bool, dict]:
    with zipfile.ZipFile(path, "r") as archive:
        bad = archive.testzip()
        files = [item for item in archive.infolist() if not item.is_dir()]
        return bad is None, {"file_count": len(files), "bad_member": bad}


async def execute_restore_verification(db: AsyncSession, actor: ActorContext, backup_run_id: UUID) -> dict:
    _require_manager(actor)
    backup = await db.get(BackupRun, backup_run_id)
    if not backup or backup.organization_id != actor.organization_id:
        raise HTTPException(404, "Backup run not found")
    if backup.status not in {BackupStatus.SUCCEEDED, BackupStatus.VERIFIED}:
        raise HTTPException(409, "Only successful backups can be verified")
    drill = RestoreDrill(organization_id=actor.organization_id, backup_run_id=backup.id, requested_by_membership_id=actor.membership_id, status=RestoreDrillStatus.RUNNING, scope="verification_only", started_at=utcnow(), metadata_json={"isolated": True, "writes_to_live_database": False})
    db.add(drill); await db.commit(); await db.refresh(drill)
    artifacts = list((await db.scalars(select(BackupArtifact).where(BackupArtifact.backup_run_id == backup.id))).all())
    result_meta: dict = {"artifacts": []}
    all_hashes = True; database_ok = not any(a.kind == BackupArtifactKind.DATABASE for a in artifacts); documents_ok = not any(a.kind == BackupArtifactKind.DOCUMENTS for a in artifacts); document_count = 0
    try:
        for artifact in artifacts:
            path = Path(artifact.storage_path)
            exists = path.is_file()
            actual_hash = await asyncio.to_thread(sha256_file, path) if exists else None
            hash_ok = bool(exists and actual_hash == artifact.sha256)
            all_hashes = all_hashes and hash_ok
            detail: dict = {"kind": str(artifact.kind), "filename": artifact.filename, "exists": exists, "hash_ok": hash_ok}
            if exists and hash_ok and artifact.kind == BackupArtifactKind.DATABASE:
                database_ok, verification = await asyncio.to_thread(_verify_database_artifact, path)
                detail["verification"] = verification
            elif exists and hash_ok and artifact.kind == BackupArtifactKind.DOCUMENTS:
                documents_ok, verification = await asyncio.to_thread(_verify_documents_artifact, path)
                document_count = int(verification.get("file_count", 0))
                detail["verification"] = verification
            elif exists and hash_ok and artifact.kind == BackupArtifactKind.MANIFEST:
                try:
                    json.loads(path.read_text(encoding="utf-8")); detail["manifest_json"] = True
                except Exception:
                    detail["manifest_json"] = False; all_hashes = False
            result_meta["artifacts"].append(detail)
        passed = all_hashes and database_ok and documents_ok
        drill.status = RestoreDrillStatus.PASSED if passed else RestoreDrillStatus.FAILED
        drill.database_verified = database_ok
        drill.documents_verified = documents_ok
        drill.artifact_hashes_verified = all_hashes
        drill.document_count_verified = document_count
        drill.finished_at = utcnow()
        drill.metadata_json = {**(drill.metadata_json or {}), **result_meta}
        drill.result_hash = canonical_hash({"passed": passed, "database": database_ok, "documents": documents_ok, "hashes": all_hashes, "count": document_count, "artifacts": result_meta["artifacts"]})
        if passed:
            backup.status = BackupStatus.VERIFIED
        await _audit(db, actor, "system.restore_verification.completed", "restore_drill", drill.id, {"backup_run_id": str(backup.id), "passed": passed, "result_hash": drill.result_hash})
        await db.commit()
        return {"restore_drill_id": str(drill.id), "status": drill.status.value, "database_verified": database_ok, "documents_verified": documents_ok, "artifact_hashes_verified": all_hashes, "result_hash": drill.result_hash}
    except Exception as exc:
        await db.rollback()
        drill = await db.get(RestoreDrill, drill.id)
        drill.status = RestoreDrillStatus.FAILED; drill.finished_at = utcnow(); drill.notes = str(exc)[:4000]
        await db.commit()
        raise


async def list_restore_drills(db: AsyncSession, actor: ActorContext, limit: int = 30) -> list[RestoreDrill]:
    _require_manager(actor)
    return list((await db.scalars(select(RestoreDrill).where(RestoreDrill.organization_id == actor.organization_id).order_by(RestoreDrill.created_at.desc()).limit(limit))).all())


async def review_restore_drill(db: AsyncSession, actor: ActorContext, drill_id: UUID, notes: str | None = None) -> RestoreDrill:
    _require_manager(actor)
    row = await db.get(RestoreDrill, drill_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Restore drill not found")
    if row.status != RestoreDrillStatus.PASSED:
        raise HTTPException(409, "Only passed restore verifications can be marked reviewed")
    row.status = RestoreDrillStatus.REVIEWED
    row.reviewed_by_membership_id = actor.membership_id
    row.reviewed_at = utcnow()
    if notes is not None:
        row.notes = notes
    await _audit(db, actor, "system.restore_verification.review", "restore_drill", row.id)
    await db.commit(); await db.refresh(row); return row


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    _require_manager(actor)
    objectives = await get_or_create_objectives(db, actor)
    latest_run = await db.scalar(select(SystemHealthRun).where(SystemHealthRun.organization_id == actor.organization_id).order_by(SystemHealthRun.started_at.desc()).limit(1))
    components: list[SystemHealthComponent] = []
    if latest_run:
        components = list((await db.scalars(select(SystemHealthComponent).where(SystemHealthComponent.run_id == latest_run.id).order_by(SystemHealthComponent.category, SystemHealthComponent.component_key))).all())
    incidents = await list_incidents(db, actor, include_resolved=False, limit=50)
    policies = await list_backup_policies(db, actor)
    backups = await list_backup_runs(db, actor, limit=12)
    drills = await list_restore_drills(db, actor, limit=12)
    metrics = await db.scalar(select(SystemMetricSnapshot).where(SystemMetricSnapshot.organization_id == actor.organization_id).order_by(SystemMetricSnapshot.captured_at.desc()).limit(1))
    return {"latest_run": latest_run, "components": components, "open_incidents": incidents, "recovery_objectives": objectives, "backup_policies": policies, "recent_backups": backups, "recent_restore_drills": drills, "latest_metrics": metrics}
