from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.deployment import (
    DeploymentChangeWindow,
    DeploymentEnvironment,
    DeploymentEnvironmentKind,
    DeploymentRollout,
    DeploymentRolloutStatus,
    DeploymentRolloutStep,
    DeploymentSecretReference,
    DeploymentServiceProfile,
    DeploymentStepKind,
    DeploymentStepStatus,
)
from app.models.release import ReleaseRun, ReleaseRunStatus, RollbackPoint, RollbackPointStatus
from app.models.security import AuditOutcome, OrganizationRole
from app.services.deployment.readiness import evaluate_runtime_readiness
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext

MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _v(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def canonical_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _require_manager(actor: ActorContext) -> None:
    if actor.role not in MANAGER_ROLES:
        raise HTTPException(403, "Partner, admin or owner role required")


async def _audit(db: AsyncSession, actor: ActorContext, action: str, resource_type: str, resource_id: UUID | None, metadata: dict | None = None) -> None:
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        outcome=AuditOutcome.SUCCESS,
        metadata=metadata or {},
    )


async def create_environment(db: AsyncSession, actor: ActorContext, **payload) -> DeploymentEnvironment:
    _require_manager(actor)
    if payload.get("kind") == DeploymentEnvironmentKind.PRODUCTION and not str(payload.get("base_url", "")).startswith("https://"):
        raise HTTPException(422, "Production base URL must use HTTPS")
    exists = await db.scalar(select(DeploymentEnvironment).where(DeploymentEnvironment.organization_id == actor.organization_id, DeploymentEnvironment.environment_key == payload["environment_key"]))
    if exists:
        raise HTTPException(409, "Deployment environment key already exists")
    row = DeploymentEnvironment(organization_id=actor.organization_id, metadata_json={}, **payload)
    db.add(row)
    await db.flush()
    defaults = [
        ("reverse-proxy", 1, "/health/live", None),
        ("web", 2, "/", None),
        ("api", 2, "/health/ready", None),
        ("worker", 2, None, "documents,search,evidence,analytics,operations,corpus,bundles,maintenance,default"),
        ("scheduler", 1, None, "maintenance"),
        ("postgres", 1, None, None),
        ("object-storage", 1, None, None),
    ]
    for key, replicas, health, queues in defaults:
        db.add(DeploymentServiceProfile(environment_id=row.id, service_key=key, replicas=replicas, health_path=health, queue_names=queues, metadata_json={}))
    await _audit(db, actor, "deployment.environment.create", "deployment_environment", row.id, {"key": row.environment_key})
    await db.commit(); await db.refresh(row)
    return row


async def list_environments(db: AsyncSession, actor: ActorContext) -> list[DeploymentEnvironment]:
    _require_manager(actor)
    return list((await db.scalars(select(DeploymentEnvironment).where(DeploymentEnvironment.organization_id == actor.organization_id).order_by(DeploymentEnvironment.kind, DeploymentEnvironment.name))).all())


async def list_services(db: AsyncSession, actor: ActorContext) -> list[DeploymentServiceProfile]:
    envs = await list_environments(db, actor)
    ids = [row.id for row in envs]
    if not ids: return []
    return list((await db.scalars(select(DeploymentServiceProfile).where(DeploymentServiceProfile.environment_id.in_(ids)).order_by(DeploymentServiceProfile.service_key))).all())


async def create_change_window(db: AsyncSession, actor: ActorContext, *, environment_id: UUID, starts_at: datetime, ends_at: datetime, reason: str, emergency: bool = False) -> DeploymentChangeWindow:
    _require_manager(actor)
    env = await _get_env(db, actor, environment_id)
    if ends_at <= starts_at: raise HTTPException(422, "Change window end must be after start")
    row = DeploymentChangeWindow(environment_id=env.id, approved_by_membership_id=actor.membership_id, starts_at=starts_at, ends_at=ends_at, reason=reason, emergency=emergency, metadata_json={})
    db.add(row); await _audit(db, actor, "deployment.change_window.create", "deployment_change_window", row.id, {"environment_id": str(env.id)}); await db.commit(); await db.refresh(row); return row


async def register_secret_reference(db: AsyncSession, actor: ActorContext, **payload) -> DeploymentSecretReference:
    _require_manager(actor)
    env = await _get_env(db, actor, payload["environment_id"])
    existing = await db.scalar(select(DeploymentSecretReference).where(DeploymentSecretReference.environment_id == env.id, DeploymentSecretReference.secret_key == payload["secret_key"]))
    if existing:
        existing.provider = payload["provider"]; existing.reference = payload["reference"]; existing.required = payload["required"]
        row = existing
    else:
        row = DeploymentSecretReference(metadata_json={}, **payload); db.add(row)
    await _audit(db, actor, "deployment.secret_reference.upsert", "deployment_secret_reference", row.id, {"secret_key": payload["secret_key"], "provider": _v(payload["provider"])})
    await db.commit(); await db.refresh(row); return row


async def _get_env(db: AsyncSession, actor: ActorContext, environment_id: UUID) -> DeploymentEnvironment:
    row = await db.get(DeploymentEnvironment, environment_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Deployment environment not found")
    return row


async def _get_rollout(db: AsyncSession, actor: ActorContext, rollout_id: UUID) -> DeploymentRollout:
    row = await db.get(DeploymentRollout, rollout_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Deployment rollout not found")
    return row


async def create_rollout(db: AsyncSession, actor: ActorContext, *, environment_id: UUID, release_run_id: UUID, rollback_point_id: UUID, change_window_id: UUID | None, notes: str | None) -> DeploymentRollout:
    _require_manager(actor)
    env = await _get_env(db, actor, environment_id)
    release = await db.get(ReleaseRun, release_run_id)
    if not release or release.organization_id != actor.organization_id: raise HTTPException(404, "Release run not found")
    if _v(release.status) != ReleaseRunStatus.APPROVED.value: raise HTTPException(409, "Release must be approved before rollout")
    rollback = await db.get(RollbackPoint, rollback_point_id)
    if not rollback or rollback.organization_id != actor.organization_id or rollback.release_run_id != release.id: raise HTTPException(409, "Rollback point must belong to the approved release")
    if _v(rollback.status) != RollbackPointStatus.READY.value or not rollback.verified_at: raise HTTPException(409, "Rollback point must be ready and verified")
    window = None
    if change_window_id:
        window = await db.get(DeploymentChangeWindow, change_window_id)
        if not window or window.environment_id != env.id: raise HTTPException(409, "Change window does not belong to environment")
    if env.change_window_required and not window: raise HTTPException(409, "This environment requires an approved change window")
    if window:
        now = utcnow()
        start = window.starts_at if window.starts_at.tzinfo else window.starts_at.replace(tzinfo=timezone.utc)
        end = window.ends_at if window.ends_at.tzinfo else window.ends_at.replace(tzinfo=timezone.utc)
        if not (start <= now <= end):
            raise HTTPException(409, "Deployment change window is not currently active")
    row = DeploymentRollout(organization_id=actor.organization_id, environment_id=env.id, release_run_id=release.id, rollback_point_id=rollback.id, change_window_id=window.id if window else None, requested_by_membership_id=actor.membership_id, status=DeploymentRolloutStatus.PLANNED, notes=notes, metadata_json={})
    db.add(row); await db.flush()
    for sequence, (key, kind) in enumerate([
        ("preflight", DeploymentStepKind.PREFLIGHT), ("backup", DeploymentStepKind.BACKUP), ("migration", DeploymentStepKind.MIGRATION), ("api", DeploymentStepKind.API), ("workers", DeploymentStepKind.WORKERS), ("web", DeploymentStepKind.WEB), ("health", DeploymentStepKind.HEALTH), ("traffic", DeploymentStepKind.TRAFFIC), ("postcheck", DeploymentStepKind.POSTCHECK),
    ], start=1):
        db.add(DeploymentRolloutStep(rollout_id=row.id, step_key=key, kind=kind, sequence=sequence, status=DeploymentStepStatus.PENDING, evidence_json={}))
    await _audit(db, actor, "deployment.rollout.create", "deployment_rollout", row.id, {"environment": env.environment_key, "release_run_id": str(release.id)})
    await db.commit(); await db.refresh(row); return row


async def update_step(db: AsyncSession, actor: ActorContext, rollout_id: UUID, step_id: UUID, *, status: DeploymentStepStatus, message: str | None, evidence_json: dict) -> DeploymentRolloutStep:
    _require_manager(actor)
    rollout = await _get_rollout(db, actor, rollout_id)
    step = await db.get(DeploymentRolloutStep, step_id)
    if not step or step.rollout_id != rollout.id: raise HTTPException(404, "Rollout step not found")
    now = utcnow()
    if status in {DeploymentStepStatus.RUNNING, DeploymentStepStatus.PASSED}:
        previous = list((await db.scalars(select(DeploymentRolloutStep).where(DeploymentRolloutStep.rollout_id == rollout.id, DeploymentRolloutStep.sequence < step.sequence).order_by(DeploymentRolloutStep.sequence))).all())
        blocking = [row.step_key for row in previous if _v(row.status) not in {DeploymentStepStatus.PASSED.value, DeploymentStepStatus.SKIPPED.value}]
        if blocking:
            raise HTTPException(409, f"Earlier rollout steps are incomplete: {', '.join(blocking)}")
    if status == DeploymentStepStatus.RUNNING and step.started_at is None: step.started_at = now
    if status in {DeploymentStepStatus.PASSED, DeploymentStepStatus.FAILED, DeploymentStepStatus.SKIPPED}: step.finished_at = now
    step.status = status; step.message = message; step.evidence_json = evidence_json
    steps = list((await db.scalars(select(DeploymentRolloutStep).where(DeploymentRolloutStep.rollout_id == rollout.id).order_by(DeploymentRolloutStep.sequence))).all())
    if rollout.started_at is None and any(_v(s.status) != DeploymentStepStatus.PENDING.value for s in steps): rollout.started_at = now
    if any(_v(s.status) == DeploymentStepStatus.FAILED.value for s in steps):
        rollout.status = DeploymentRolloutStatus.FAILED; rollout.finished_at = now
    elif all(_v(s.status) in {DeploymentStepStatus.PASSED.value, DeploymentStepStatus.SKIPPED.value} for s in steps):
        rollout.status = DeploymentRolloutStatus.SUCCEEDED; rollout.finished_at = now
        env = await db.get(DeploymentEnvironment, rollout.environment_id); env.current_release_run_id = rollout.release_run_id
        rollout.snapshot_hash = canonical_hash({"rollout": str(rollout.id), "release": str(rollout.release_run_id), "steps": [(s.step_key, _v(s.status), s.evidence_json) for s in steps]})
    else:
        rollout.status = DeploymentRolloutStatus.RUNNING
    await _audit(db, actor, "deployment.rollout.step", "deployment_rollout", rollout.id, {"step": step.step_key, "status": _v(status)})
    await db.commit(); await db.refresh(step); return step


async def rollout_detail(db: AsyncSession, actor: ActorContext, rollout_id: UUID) -> dict:
    rollout = await _get_rollout(db, actor, rollout_id)
    steps = list((await db.scalars(select(DeploymentRolloutStep).where(DeploymentRolloutStep.rollout_id == rollout.id).order_by(DeploymentRolloutStep.sequence))).all())
    return {"rollout": rollout, "steps": steps}


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    _require_manager(actor)
    envs = await list_environments(db, actor)
    env_ids = [e.id for e in envs]
    services = await list_services(db, actor)
    rollouts = list((await db.scalars(select(DeploymentRollout).where(DeploymentRollout.organization_id == actor.organization_id).order_by(DeploymentRollout.created_at.desc()).limit(20))).all())
    windows = list((await db.scalars(select(DeploymentChangeWindow).where(DeploymentChangeWindow.environment_id.in_(env_ids)).order_by(DeploymentChangeWindow.starts_at.desc()).limit(20))).all()) if env_ids else []
    secrets = list((await db.scalars(select(DeploymentSecretReference).where(DeploymentSecretReference.environment_id.in_(env_ids)).order_by(DeploymentSecretReference.secret_key))).all()) if env_ids else []
    return {"environments": envs, "services": services, "rollouts": rollouts, "change_windows": windows, "secrets": secrets, "runtime_readiness": evaluate_runtime_readiness(settings)}
