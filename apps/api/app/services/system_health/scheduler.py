from __future__ import annotations

from datetime import timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.jobs import JobKind, JobPriority
from app.models.legal_data_ops import LegalDataFeed, LegalDataFeedMode
from app.models.security import MembershipStatus, OrganizationMembership, OrganizationRole, SecurityUser
from app.models.system_health import BackupPolicy, SystemHealthRun
from app.services.jobs import service as jobs_service
from app.services.security.context import ActorContext
from app.services.system_health.engine import age_seconds, schedule_due, utcnow

MANAGER_ROLES = [OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER]


async def scheduler_actor(db: AsyncSession, organization_id: UUID) -> ActorContext:
    membership = await db.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
            OrganizationMembership.role.in_(MANAGER_ROLES),
        )
        .order_by(OrganizationMembership.is_default.desc(), OrganizationMembership.created_at)
        .limit(1)
    )
    if membership is None:
        raise HTTPException(409, "No active owner/admin/partner membership is available to own scheduled maintenance jobs")
    user = await db.get(SecurityUser, membership.user_id)
    if user is None:
        raise HTTPException(409, "Scheduled maintenance membership has no active user record")
    return ActorContext(
        user_id=user.id,
        membership_id=membership.id,
        organization_id=membership.organization_id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        mfa_enrolled=user.mfa_enrolled,
        session_id=None,
    )


async def tick(db: AsyncSession, organization_id: UUID) -> dict:
    actor = await scheduler_actor(db, organization_id)
    now = utcnow()
    queued: list[dict] = []

    last_health = await db.scalar(
        select(SystemHealthRun)
        .where(SystemHealthRun.organization_id == organization_id)
        .order_by(SystemHealthRun.started_at.desc())
        .limit(1)
    )
    health_age = age_seconds(now, last_health.started_at if last_health else None)
    health_interval = max(1, settings.system_health_check_interval_minutes) * 60
    if health_age is None or health_age >= health_interval:
        bucket = int(now.timestamp() // health_interval)
        job = await jobs_service.enqueue(
            db,
            actor,
            kind=JobKind.SYSTEM_HEALTH_CHECK,
            payload={},
            priority=JobPriority.NORMAL,
            resource_type="system_health",
            idempotency_key=f"scheduled-health:{bucket}",
        )
        queued.append({"kind": job.kind.value if hasattr(job.kind, "value") else str(job.kind), "job_id": str(job.id)})

    policies = list((await db.scalars(select(BackupPolicy).where(BackupPolicy.organization_id == organization_id, BackupPolicy.enabled.is_(True)))).all())
    for policy in policies:
        if not schedule_due(last_run_at=policy.last_run_at, rule=policy.schedule_rrule, now=now):
            continue
        bucket_size = 3600
        bucket = int(now.timestamp() // bucket_size)
        job = await jobs_service.enqueue(
            db,
            actor,
            kind=JobKind.BACKUP_RUN,
            payload={"policy_id": str(policy.id)},
            priority=JobPriority.HIGH,
            resource_type="backup_policy",
            resource_id=policy.id,
            idempotency_key=f"scheduled-backup:{policy.id}:{bucket}",
        )
        queued.append({"kind": job.kind.value if hasattr(job.kind, "value") else str(job.kind), "job_id": str(job.id), "policy_id": str(policy.id)})

    # Batch 26 · legal-data maintenance. Only controlled filesystem-drop feeds are pulled
    # by the scheduler; manual/integration feeds remain push-only and no protected site is scraped.
    due_feeds = list((await db.scalars(
        select(LegalDataFeed).where(
            LegalDataFeed.organization_id == organization_id,
            LegalDataFeed.enabled.is_(True),
            LegalDataFeed.mode == LegalDataFeedMode.FILESYSTEM_DROP,
            (LegalDataFeed.next_due_at.is_(None)) | (LegalDataFeed.next_due_at <= now),
        )
    )).all())
    for feed in due_feeds:
        bucket_seconds = max(300, int(feed.schedule_interval_minutes) * 60)
        bucket = int(now.timestamp() // bucket_seconds)
        job = await jobs_service.enqueue(
            db, actor, kind=JobKind.LEGAL_DATA_FEED_SYNC, payload={"feed_id": str(feed.id)},
            priority=JobPriority.NORMAL, resource_type="legal_data_feed", resource_id=feed.id,
            idempotency_key=f"scheduled-legal-feed:{feed.id}:{bucket}",
        )
        queued.append({"kind": job.kind.value if hasattr(job.kind, "value") else str(job.kind), "job_id": str(job.id), "feed_id": str(feed.id)})

    sweep_seconds = max(300, int(settings.legal_data_stale_sweep_minutes) * 60)
    sweep_bucket = int(now.timestamp() // sweep_seconds)
    job = await jobs_service.enqueue(
        db, actor, kind=JobKind.LEGAL_DATA_INTEGRITY_SWEEP, payload={}, priority=JobPriority.LOW,
        resource_type="legal_data_integrity", idempotency_key=f"scheduled-legal-integrity:{sweep_bucket}",
    )
    queued.append({"kind": job.kind.value if hasattr(job.kind, "value") else str(job.kind), "job_id": str(job.id)})

    return {"organization_id": str(organization_id), "checked_at": now.astimezone(timezone.utc).isoformat(), "queued": queued, "queued_count": len(queued)}
