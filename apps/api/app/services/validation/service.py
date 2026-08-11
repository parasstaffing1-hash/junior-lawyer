from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.deployment import DeploymentEnvironment, DeploymentEnvironmentKind
from app.models.release import (
    ReleaseArtifact,
    ReleaseArtifactKind,
    ReleaseRun,
    ReleaseRunStatus,
    RollbackPoint,
    RollbackPointStatus,
)
from app.models.security import AuditOutcome, OrganizationRole
from app.models.validation import (
    PilotCheckStatus,
    PilotReadinessCheck,
    ReleaseCandidateManifest,
    ReleaseCandidateStatus,
    ValidationCampaign,
    ValidationCampaignStatus,
    ValidationDataset,
    ValidationEvidence,
    ValidationExecutionMode,
    ValidationRunStatus,
    ValidationScenario,
    ValidationScenarioKind,
    ValidationScenarioRun,
    ValidationSeverity,
    ValidationSignoff,
    ValidationSignoffDecision,
)
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext
from app.services.validation.engine import (
    PilotGateRow,
    ScenarioGateRow,
    build_candidate_manifest,
    canonical_hash,
    evaluate_numeric_thresholds,
    evaluate_validation_gate,
    value_of,
)

MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}
DATABASE_REVISION = "20260808_0028"

DEFAULT_SCENARIOS = [
    {
        "scenario_key": "postgres_minio_staging",
        "name": "PostgreSQL + object-storage staging boot",
        "description": "Boot the hardened staging topology with PostgreSQL, S3-compatible storage, API, web, workers and scheduler.",
        "kind": ValidationScenarioKind.DEPLOYMENT,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.CRITICAL,
        "thresholds_json": {"equals": {"healthy": True}},
        "instructions_json": {"evidence": ["service health report", "migration revision", "object-storage read/write proof"]},
    },
    {
        "scenario_key": "bilingual_core_e2e",
        "name": "English + Hindi end-to-end legal workflow",
        "description": "Create matter, upload English/Hindi material, extract, search, draft and review with source provenance.",
        "kind": ValidationScenarioKind.BILINGUAL,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.CRITICAL,
        "thresholds_json": {"equals": {"english_flow": True, "hindi_flow": True, "provenance_preserved": True}},
        "instructions_json": {"languages": ["en", "hi", "hinglish"]},
    },
    {
        "scenario_key": "case_lookup_remedy_e2e",
        "name": "Case Lookup + Legal Remedy Analysis end-to-end",
        "description": "Resolve exact CNR and ambiguous case-number inputs, import/refresh a normalized official case snapshot, detect changes, and run only verified remedy rules with source-backed deadlines/maintainability before memo/draft generation.",
        "kind": ValidationScenarioKind.E2E,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.CRITICAL,
        "thresholds_json": {"max": {"unsupported_remedies": 0, "uncited_active_rules": 0}, "equals": {"cnr_exact": True, "ambiguity_preserved": True, "change_detection": True, "lawyer_review_gate": True}},
        "instructions_json": {"languages": ["en", "hi", "hinglish"], "no_captcha_bypass": True, "official_lookup": "approved connector or user-assisted flow"},
    },
    {
        "scenario_key": "ethical_wall_authenticated",
        "name": "Authenticated ethical-wall penetration matrix",
        "description": "Verify restricted matter/client/document identifiers do not leak through direct IDs, search, recents, aggregates or exports.",
        "kind": ValidationScenarioKind.SECURITY,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.CRITICAL,
        "thresholds_json": {"max": {"leaks": 0}, "equals": {"idor_blocked": True}},
        "instructions_json": {"zero_tolerance": True},
    },
    {
        "scenario_key": "session_csrf_portal_boundary",
        "name": "Session, CSRF and client-portal trust boundary",
        "description": "Exercise internal and external sessions, CSRF failures, revocation and portal resource enumeration controls.",
        "kind": ValidationScenarioKind.SECURITY,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.CRITICAL,
        "thresholds_json": {"max": {"critical_failures": 0}},
        "instructions_json": {"zero_tolerance": True},
    },
    {
        "scenario_key": "backup_restore_isolated",
        "name": "Full backup → isolated restore verification",
        "description": "Back up database and file/object storage, verify hashes, restore into an isolated target and confirm integrity without touching live data.",
        "kind": ValidationScenarioKind.RECOVERY,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.CRITICAL,
        "thresholds_json": {"equals": {"database_verified": True, "files_verified": True, "live_untouched": True}},
        "instructions_json": {"requires": ["backup hash", "restore report", "RPO/RTO observation"]},
    },
    {
        "scenario_key": "large_document_1000_pages",
        "name": "1,000-page bilingual document workflow",
        "description": "Validate bounded reader windows, OCR/extraction, page search and incremental indexing on a synthetic or de-identified large document.",
        "kind": ValidationScenarioKind.LARGE_DOCUMENT,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.REQUIRED,
        "thresholds_json": {"min": {"pages": 1000, "reader_success_rate": 0.99}},
        "instructions_json": {"no_real_client_data_required": True},
    },
    {
        "scenario_key": "search_100k_documents",
        "name": "100k-document indexed-search validation",
        "description": "Run hybrid search against a representative synthetic/de-identified corpus and record latency/relevance metrics.",
        "kind": ValidationScenarioKind.LOAD,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.REQUIRED,
        "thresholds_json": {"min": {"documents": 100000, "success_rate": 0.99}, "max": {"p95_ms": 1500}},
        "instructions_json": {"hardware_must_be_recorded": True},
    },
    {
        "scenario_key": "worker_queue_saturation",
        "name": "Worker saturation + recovery",
        "description": "Stress document/search/evidence queues, verify lease recovery, backoff and dead-letter behavior under bounded saturation.",
        "kind": ValidationScenarioKind.WORKERS,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.REQUIRED,
        "thresholds_json": {"max": {"lost_jobs": 0}, "equals": {"lease_recovery": True}},
        "instructions_json": {"bounded_test": True},
    },
    {
        "scenario_key": "accessibility_keyboard_screenreader",
        "name": "Keyboard + screen-reader accessibility pass",
        "description": "Validate focus order, dialogs, landmarks, keyboard-only primary workflows and Hindi/English labels on representative browsers.",
        "kind": ValidationScenarioKind.ACCESSIBILITY,
        "execution_mode": ValidationExecutionMode.MANUAL,
        "severity": ValidationSeverity.REQUIRED,
        "thresholds_json": {"max": {"blocking_issues": 0}},
        "instructions_json": {"assistive_tech": ["NVDA or equivalent", "keyboard-only"]},
    },
    {
        "scenario_key": "legal_corpus_integrity",
        "name": "Legal corpus source/version integrity",
        "description": "Verify authoritative-domain enforcement, hashes, historical section versioning and pending-amendment review behavior.",
        "kind": ValidationScenarioKind.DATA_INTEGRITY,
        "execution_mode": ValidationExecutionMode.STAGING,
        "severity": ValidationSeverity.REQUIRED,
        "thresholds_json": {"max": {"unverified_required_sources": 0, "hash_failures": 0}},
        "instructions_json": {"no_captcha_bypass": True},
    },
]

DEFAULT_PILOT_CHECKS = [
    ("pilot_owner", "people", "Named pilot owner and escalation contact", True),
    ("pilot_lawyers_trained", "people", "Pilot lawyers trained on review gates and source provenance", True),
    ("support_channel", "operations", "Pilot support/incident channel is ready", True),
    ("privacy_notice", "governance", "Privacy/confidentiality notice reviewed for pilot use", True),
    ("ai_policy", "governance", "Remote-AI policy configured; privileged matters default-deny where required", True),
    ("legal_data_sources", "legal_data", "Required legal-data sources/jurisdiction packs reviewed", True),
    ("remedy_rule_packs", "legal_data", "Active Legal Remedy rule packs reviewed; each active rule has verified authority and limitation/forum metadata is lawyer-approved", True),
    ("offsite_backup", "recovery", "Production/pilot backups are stored off the application host", True),
    ("restore_owner", "recovery", "Named owner can execute the restore runbook", True),
    ("rollback_proof", "release", "Verified rollback point exists for the candidate", True),
    ("known_limitations", "release", "Known limitations and lawyer-review boundaries provided to pilot users", True),
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


async def seed_scenarios(db: AsyncSession, actor: ActorContext) -> list[ValidationScenario]:
    _require_manager(actor)
    rows: list[ValidationScenario] = []
    for item in DEFAULT_SCENARIOS:
        row = await db.scalar(select(ValidationScenario).where(ValidationScenario.organization_id == actor.organization_id, ValidationScenario.scenario_key == item["scenario_key"]))
        if row is None:
            row = ValidationScenario(organization_id=actor.organization_id, enabled=True, **item)
            db.add(row)
        else:
            for key, value in item.items():
                setattr(row, key, value)
            row.enabled = True
        rows.append(row)
    await db.flush()
    await _audit(db, actor, "validation.scenarios.seed", "validation_scenario", None, {"count": len(rows)})
    await db.commit()
    return rows


async def _scenarios(db: AsyncSession, actor: ActorContext) -> list[ValidationScenario]:
    return list((await db.scalars(select(ValidationScenario).where(ValidationScenario.organization_id == actor.organization_id, ValidationScenario.enabled.is_(True)).order_by(ValidationScenario.severity.desc(), ValidationScenario.name))).all())


async def create_campaign(db: AsyncSession, actor: ActorContext, *, name: str, candidate_version: str, release_run_id: UUID | None, environment_id: UUID | None, build_ref: str | None) -> ValidationCampaign:
    _require_manager(actor)
    if not await _scenarios(db, actor):
        await seed_scenarios(db, actor)
    if release_run_id:
        release = await db.get(ReleaseRun, release_run_id)
        if not release or release.organization_id != actor.organization_id:
            raise HTTPException(404, "Release run not found")
    if environment_id:
        env = await db.get(DeploymentEnvironment, environment_id)
        if not env or env.organization_id != actor.organization_id:
            raise HTTPException(404, "Deployment environment not found")
    row = ValidationCampaign(
        organization_id=actor.organization_id,
        release_run_id=release_run_id,
        environment_id=environment_id,
        name=name,
        candidate_version=candidate_version,
        build_ref=build_ref,
        status=ValidationCampaignStatus.RUNNING,
        started_at=utcnow(),
        summary_json={"minimum_signoffs": 1},
    )
    db.add(row)
    await db.flush()
    for key, category, label, required in DEFAULT_PILOT_CHECKS:
        db.add(PilotReadinessCheck(campaign_id=row.id, check_key=key, category=category, label=label, required=required, status=PilotCheckStatus.PENDING, evidence_json={}))
    await _audit(db, actor, "validation.campaign.create", "validation_campaign", row.id, {"candidate_version": candidate_version})
    await db.commit(); await db.refresh(row)
    return row


async def list_campaigns(db: AsyncSession, actor: ActorContext, limit: int = 30) -> list[ValidationCampaign]:
    _require_manager(actor)
    return list((await db.scalars(select(ValidationCampaign).where(ValidationCampaign.organization_id == actor.organization_id).order_by(ValidationCampaign.created_at.desc()).limit(limit))).all())


async def _campaign(db: AsyncSession, actor: ActorContext, campaign_id: UUID) -> ValidationCampaign:
    _require_manager(actor)
    row = await db.get(ValidationCampaign, campaign_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Validation campaign not found")
    return row


async def record_scenario_result(db: AsyncSession, actor: ActorContext, campaign_id: UUID, *, scenario_id: UUID, status: ValidationRunStatus, duration_ms: int, metrics_json: dict, details_json: dict, error: str | None) -> ValidationScenarioRun:
    campaign = await _campaign(db, actor, campaign_id)
    scenario = await db.get(ValidationScenario, scenario_id)
    if not scenario or scenario.organization_id != actor.organization_id or not scenario.enabled:
        raise HTTPException(404, "Validation scenario not found")
    passed_thresholds, threshold_reasons = evaluate_numeric_thresholds(metrics_json, scenario.thresholds_json)
    effective_status = status
    if value_of(status) == ValidationRunStatus.PASSED.value and not passed_thresholds:
        effective_status = ValidationRunStatus.FAILED
        details_json = {**details_json, "threshold_failures": threshold_reasons}
        error = error or "; ".join(threshold_reasons)
    row = await db.scalar(select(ValidationScenarioRun).where(ValidationScenarioRun.campaign_id == campaign.id, ValidationScenarioRun.scenario_id == scenario.id))
    now = utcnow()
    snapshot = {
        "campaign": str(campaign.id), "scenario": scenario.scenario_key, "status": value_of(effective_status),
        "metrics": metrics_json, "details": details_json, "error": error,
    }
    if row is None:
        row = ValidationScenarioRun(campaign_id=campaign.id, scenario_id=scenario.id)
        db.add(row)
    row.status = effective_status
    row.started_at = row.started_at or now
    row.finished_at = now if value_of(effective_status) in {"passed", "failed", "blocked", "skipped"} else None
    row.duration_ms = duration_ms
    row.metrics_json = metrics_json
    row.details_json = details_json
    row.error = error
    row.snapshot_hash = canonical_hash(snapshot)
    campaign.status = ValidationCampaignStatus.RUNNING
    await _audit(db, actor, "validation.scenario.record", "validation_scenario_run", row.id, {"scenario": scenario.scenario_key, "status": value_of(effective_status)})
    await db.commit(); await db.refresh(row)
    return row


async def add_evidence(db: AsyncSession, actor: ActorContext, scenario_run_id: UUID, **payload) -> ValidationEvidence:
    _require_manager(actor)
    run = await db.get(ValidationScenarioRun, scenario_run_id)
    if not run:
        raise HTTPException(404, "Scenario run not found")
    campaign = await _campaign(db, actor, run.campaign_id)
    _ = campaign
    row = ValidationEvidence(scenario_run_id=run.id, **payload)
    db.add(row)
    await _audit(db, actor, "validation.evidence.add", "validation_evidence", row.id, {"label": row.label})
    await db.commit(); await db.refresh(row)
    return row


async def update_pilot_check(db: AsyncSession, actor: ActorContext, campaign_id: UUID, check_id: UUID, *, status: PilotCheckStatus, note: str | None, evidence_json: dict) -> PilotReadinessCheck:
    campaign = await _campaign(db, actor, campaign_id)
    row = await db.get(PilotReadinessCheck, check_id)
    if not row or row.campaign_id != campaign.id:
        raise HTTPException(404, "Pilot readiness check not found")
    if value_of(status) == PilotCheckStatus.WAIVED.value and row.required and actor.role not in {OrganizationRole.OWNER, OrganizationRole.PARTNER}:
        raise HTTPException(403, "Only an owner or partner may waive a required pilot check")
    row.status = status; row.note = note; row.evidence_json = evidence_json; row.reviewed_by_membership_id = actor.membership_id; row.reviewed_at = utcnow()
    await _audit(db, actor, "validation.pilot_check.update", "pilot_readiness_check", row.id, {"check": row.check_key, "status": value_of(status)})
    await db.commit(); await db.refresh(row)
    return row


async def add_dataset(db: AsyncSession, actor: ActorContext, campaign_id: UUID, **payload) -> ValidationDataset:
    campaign = await _campaign(db, actor, campaign_id)
    row = ValidationDataset(organization_id=actor.organization_id, campaign_id=campaign.id, **payload)
    db.add(row)
    await _audit(db, actor, "validation.dataset.add", "validation_dataset", row.id, {"kind": value_of(row.kind), "name": row.name})
    await db.commit(); await db.refresh(row)
    return row


async def signoff(db: AsyncSession, actor: ActorContext, campaign_id: UUID, *, decision: ValidationSignoffDecision, role_label: str, note: str | None) -> ValidationSignoff:
    campaign = await _campaign(db, actor, campaign_id)
    existing = await db.scalar(select(ValidationSignoff).where(ValidationSignoff.campaign_id == campaign.id, ValidationSignoff.membership_id == actor.membership_id))
    if existing is None:
        existing = ValidationSignoff(campaign_id=campaign.id, membership_id=actor.membership_id, decision=decision, role_label=role_label, note=note, decided_at=utcnow())
        db.add(existing)
    else:
        existing.decision = decision; existing.role_label = role_label; existing.note = note; existing.decided_at = utcnow()
    await _audit(db, actor, "validation.signoff", "validation_campaign", campaign.id, {"decision": value_of(decision), "role_label": role_label})
    await db.commit(); await db.refresh(existing)
    return existing


async def _gate_inputs(db: AsyncSession, actor: ActorContext, campaign: ValidationCampaign) -> dict:
    scenarios = await _scenarios(db, actor)
    runs = list((await db.scalars(select(ValidationScenarioRun).where(ValidationScenarioRun.campaign_id == campaign.id))).all())
    run_by_scenario = {row.scenario_id: row for row in runs}
    checks = list((await db.scalars(select(PilotReadinessCheck).where(PilotReadinessCheck.campaign_id == campaign.id).order_by(PilotReadinessCheck.category, PilotReadinessCheck.label))).all())
    signoffs = list((await db.scalars(select(ValidationSignoff).where(ValidationSignoff.campaign_id == campaign.id))).all())
    datasets = list((await db.scalars(select(ValidationDataset).where(ValidationDataset.campaign_id == campaign.id).order_by(ValidationDataset.created_at))).all())

    release_approved = False; rollback_verified = False; release_hash = None; artifact_sha = None
    if campaign.release_run_id:
        release = await db.get(ReleaseRun, campaign.release_run_id)
        if release and release.organization_id == actor.organization_id:
            release_approved = value_of(release.status) == ReleaseRunStatus.APPROVED.value
            release_hash = release.snapshot_hash
            rollback = await db.scalar(select(RollbackPoint).where(RollbackPoint.organization_id == actor.organization_id, RollbackPoint.release_run_id == release.id, RollbackPoint.status == RollbackPointStatus.READY).order_by(RollbackPoint.verified_at.desc()))
            rollback_verified = bool(rollback and rollback.verified_at)
            artifact = await db.scalar(select(ReleaseArtifact).where(ReleaseArtifact.release_run_id == release.id, ReleaseArtifact.kind == ReleaseArtifactKind.SOURCE_ZIP).order_by(ReleaseArtifact.created_at.desc()))
            artifact_sha = artifact.sha256 if artifact else None

    staging_environment = False
    if campaign.environment_id:
        env = await db.get(DeploymentEnvironment, campaign.environment_id)
        staging_environment = bool(env and env.organization_id == actor.organization_id and value_of(env.kind) == DeploymentEnvironmentKind.STAGING.value and env.enabled)

    scenario_gate = [ScenarioGateRow(s.scenario_key, value_of(s.severity), value_of(run_by_scenario[s.id].status) if s.id in run_by_scenario else ValidationRunStatus.PENDING.value) for s in scenarios]
    check_gate = [PilotGateRow(c.check_key, c.required, value_of(c.status)) for c in checks]
    approvals = sum(1 for row in signoffs if value_of(row.decision) == ValidationSignoffDecision.APPROVE.value)
    rejections = sum(1 for row in signoffs if value_of(row.decision) == ValidationSignoffDecision.REJECT.value)
    minimum_signoffs = int((campaign.summary_json or {}).get("minimum_signoffs", 1))
    passed, reasons = evaluate_validation_gate(
        scenario_gate, check_gate,
        release_approved=release_approved,
        rollback_verified=rollback_verified,
        staging_environment=staging_environment,
        artifact_integrity=bool(artifact_sha),
        minimum_signoffs=minimum_signoffs,
        approval_signoffs=approvals,
        rejection_signoffs=rejections,
    )
    return {
        "passed": passed,
        "reasons": reasons,
        "release_approved": release_approved,
        "rollback_verified": rollback_verified,
        "staging_environment": staging_environment,
        "artifact_integrity": bool(artifact_sha),
        "artifact_sha256": artifact_sha,
        "release_hash": release_hash,
        "minimum_signoffs": minimum_signoffs,
        "approval_signoffs": approvals,
        "rejection_signoffs": rejections,
        "scenarios": scenarios,
        "runs": runs,
        "checks": checks,
        "signoffs": signoffs,
        "datasets": datasets,
    }


async def evaluate_campaign(db: AsyncSession, actor: ActorContext, campaign_id: UUID) -> dict:
    campaign = await _campaign(db, actor, campaign_id)
    gate = await _gate_inputs(db, actor, campaign)
    summary = {
        "passed": gate["passed"],
        "reasons": gate["reasons"],
        "scenario_total": len(gate["scenarios"]),
        "scenario_passed": sum(1 for r in gate["runs"] if value_of(r.status) == ValidationRunStatus.PASSED.value),
        "pilot_checks": len(gate["checks"]),
        "pilot_passed": sum(1 for c in gate["checks"] if value_of(c.status) in {PilotCheckStatus.PASSED.value, PilotCheckStatus.WAIVED.value}),
        "release_approved": gate["release_approved"],
        "rollback_verified": gate["rollback_verified"],
        "staging_environment": gate["staging_environment"],
        "artifact_integrity": gate["artifact_integrity"],
        "approval_signoffs": gate["approval_signoffs"],
        "rejection_signoffs": gate["rejection_signoffs"],
        "minimum_signoffs": gate["minimum_signoffs"],
    }
    campaign.summary_json = summary
    campaign.snapshot_hash = canonical_hash({"campaign": str(campaign.id), "candidate_version": campaign.candidate_version, "summary": summary, "runs": sorted((str(r.scenario_id), value_of(r.status), r.snapshot_hash) for r in gate["runs"])})
    campaign.status = ValidationCampaignStatus.APPROVED if gate["passed"] else ValidationCampaignStatus.HELD
    campaign.finished_at = utcnow() if gate["passed"] else None

    manifest_payload = build_candidate_manifest(
        candidate_version=campaign.candidate_version,
        app_version=settings.app_version,
        database_revision=DATABASE_REVISION,
        artifact_sha256=gate["artifact_sha256"],
        campaign_hash=campaign.snapshot_hash,
        release_hash=gate["release_hash"],
        validation_summary=summary,
        datasets=[{"kind": value_of(d.kind), "name": d.name, "sha256": d.sha256} for d in gate["datasets"]],
    )
    manifest = await db.scalar(select(ReleaseCandidateManifest).where(ReleaseCandidateManifest.campaign_id == campaign.id))
    if manifest is None:
        manifest = ReleaseCandidateManifest(
            campaign_id=campaign.id,
            release_run_id=campaign.release_run_id,
            environment_id=campaign.environment_id,
            candidate_version=campaign.candidate_version,
            database_revision=DATABASE_REVISION,
            artifact_sha256=gate["artifact_sha256"],
            status=ReleaseCandidateStatus.APPROVED if gate["passed"] else ReleaseCandidateStatus.HELD,
            gate_json=summary,
            manifest_json=manifest_payload,
            snapshot_hash=manifest_payload["snapshot_hash"],
        ); db.add(manifest)
    else:
        manifest.release_run_id = campaign.release_run_id; manifest.environment_id = campaign.environment_id
        manifest.candidate_version = campaign.candidate_version; manifest.database_revision = DATABASE_REVISION
        manifest.artifact_sha256 = gate["artifact_sha256"]; manifest.status = ReleaseCandidateStatus.APPROVED if gate["passed"] else ReleaseCandidateStatus.HELD
        manifest.gate_json = summary; manifest.manifest_json = manifest_payload; manifest.snapshot_hash = manifest_payload["snapshot_hash"]
    await _audit(db, actor, "validation.campaign.evaluate", "validation_campaign", campaign.id, {"passed": gate["passed"], "reasons": gate["reasons"]})
    await db.commit(); await db.refresh(campaign); await db.refresh(manifest)
    return {"campaign": campaign, "manifest": manifest, "gate": summary}


async def detail(db: AsyncSession, actor: ActorContext, campaign_id: UUID) -> dict:
    campaign = await _campaign(db, actor, campaign_id)
    gate = await _gate_inputs(db, actor, campaign)
    manifest = await db.scalar(select(ReleaseCandidateManifest).where(ReleaseCandidateManifest.campaign_id == campaign.id))
    return {"campaign": campaign, "scenarios": gate["scenarios"], "runs": gate["runs"], "checks": gate["checks"], "datasets": gate["datasets"], "signoffs": gate["signoffs"], "manifest": manifest, "gate": {k: v for k, v in gate.items() if k not in {"scenarios", "runs", "checks", "datasets", "signoffs"}}}


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    _require_manager(actor)
    scenarios = await _scenarios(db, actor)
    campaigns = await list_campaigns(db, actor, limit=20)
    latest = campaigns[0] if campaigns else None
    return {
        "scenarios": scenarios,
        "campaigns": campaigns,
        "summary": {
            "app_version": settings.app_version,
            "database_revision": DATABASE_REVISION,
            "scenario_count": len(scenarios),
            "critical_scenarios": sum(1 for s in scenarios if value_of(s.severity) == ValidationSeverity.CRITICAL.value),
            "latest_status": value_of(latest.status) if latest else None,
            "latest_candidate": latest.candidate_version if latest else None,
            "feature_freeze": True,
        },
    }
