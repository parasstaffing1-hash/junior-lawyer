from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa import ReleaseQualityGateRun
from app.models.release import (
    DeploymentApproval,
    DeploymentDecision,
    PerformanceRun,
    PerformanceRunStatus,
    PerformanceScenario,
    PerformanceScenarioKind,
    ReleaseArtifact,
    ReleaseArtifactKind,
    ReleasePipeline,
    ReleaseRun,
    ReleaseRunStatus,
    ReleaseStageKind,
    ReleaseStageRun,
    ReleaseStageStatus,
    RollbackPoint,
    RollbackPointStatus,
    SecurityCheckKind,
    SecurityRunStatus,
    SecurityTestCase,
    SecurityTestRun,
)
from app.models.security import AuditOutcome, OrganizationRole
from app.services.release.engine import (
    ReleaseGateInput,
    canonical_hash,
    decide_release_gate,
    evaluate_performance,
    evaluate_security_result,
    summarize_latencies,
)
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext

APP_VERSION = "0.29.0-rc.1"
MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


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


async def get_or_create_pipeline(db: AsyncSession, actor: ActorContext) -> ReleasePipeline:
    _require_manager(actor)
    row = await db.scalar(
        select(ReleasePipeline).where(
            ReleasePipeline.organization_id == actor.organization_id,
            ReleasePipeline.pipeline_key == "production-release",
        )
    )
    if row:
        return row
    row = ReleasePipeline(
        organization_id=actor.organization_id,
        pipeline_key="production-release",
        name="Production release gate",
        version=1,
        thresholds_json={
            "api_smoke_p95_ms": 750,
            "search_p95_ms": 1200,
            "minimum_success_rate": 0.99,
            "maximum_error_rate": 0.01,
        },
        metadata_json={
            "principle": "legal QA and critical security failures cannot be averaged away",
            "notes": "Load thresholds are starter defaults and should be replaced by measured deployment SLOs.",
        },
    )
    db.add(row)
    await db.flush()
    await _seed_performance(db, actor)
    await _seed_security(db, actor)
    await _audit(db, actor, "release.pipeline.seed", "release_pipeline", row.id)
    await db.commit()
    await db.refresh(row)
    return row


async def _seed_performance(db: AsyncSession, actor: ActorContext) -> None:
    existing = set((await db.scalars(select(PerformanceScenario.scenario_key).where(PerformanceScenario.organization_id == actor.organization_id))).all())
    rows = [
        dict(scenario_key="api-health-smoke", name="API health concurrent smoke", kind=PerformanceScenarioKind.API_SMOKE, method="GET", path="/health", concurrency=16, request_count=250, max_p95_ms=750, min_success_rate=0.999, max_error_rate=0.001, critical=True),
        dict(scenario_key="universal-search", name="Universal search concurrency", kind=PerformanceScenarioKind.SEARCH_CONCURRENCY, method="GET", path="/api/v1/search?q=agreement", concurrency=20, request_count=300, max_p95_ms=1200, min_success_rate=0.99, max_error_rate=0.01, critical=True),
        dict(scenario_key="worker-queue-primitives", name="Worker queue saturation primitives", kind=PerformanceScenarioKind.WORKER_QUEUE, method="INTERNAL", path="jobs.claim", concurrency=8, request_count=500, max_p95_ms=500, min_success_rate=0.99, max_error_rate=0.01, critical=False),
    ]
    for payload in rows:
        if payload["scenario_key"] not in existing:
            db.add(PerformanceScenario(organization_id=actor.organization_id, timeout_seconds=15.0, payload_json={}, headers_json={}, metadata_json={}, **payload))


async def _seed_security(db: AsyncSession, actor: ActorContext) -> None:
    existing = set((await db.scalars(select(SecurityTestCase.case_key).where(SecurityTestCase.organization_id == actor.organization_id))).all())
    rows = [
        dict(case_key="protected-api-rejects-anonymous", title="Protected API rejects anonymous sessions", kind=SecurityCheckKind.AUTHORIZATION, request_json={"method":"GET","path":"/api/v1/security/me","anonymous":True}, expected_json={"status_in":[401,403]}, description="When authentication enforcement is enabled, internal security endpoints must not be anonymous."),
        dict(case_key="csrf-mutation-rejected", title="Mutation requires CSRF protection", kind=SecurityCheckKind.CSRF, request_json={"method":"POST","path":"/api/v1/matters","omit_csrf":True}, expected_json={"status_in":[401,403,419]}, description="An authenticated browser mutation without the CSRF token must be rejected."),
        dict(case_key="ethical-wall-no-title-leak", title="Ethical-wall titles never leak", kind=SecurityCheckKind.ETHICAL_WALL, request_json={"mode":"deterministic_policy"}, expected_json={"forbidden_strings_absent":["Secret Acquisition Client XYZ"]}, description="Restricted matter/client identifiers must not appear in search/dashboard output."),
        dict(case_key="idor-not-found-or-denied", title="Cross-matter IDOR is denied", kind=SecurityCheckKind.IDOR, request_json={"mode":"authenticated_fixture"}, expected_json={"status_in":[403,404]}, description="A known object UUID outside the actor's scope must not become readable."),
        dict(case_key="prompt-injection-stays-evidence", title="Document prompt injection stays untrusted evidence", kind=SecurityCheckKind.PROMPT_INJECTION, request_json={"mode":"deterministic_prompt_policy"}, expected_json={"json_equals":{"untrusted_sources":True}}, description="Instructions embedded inside uploaded legal material cannot override the AI system policy."),
        dict(case_key="security-headers-baseline", title="Security response headers baseline", kind=SecurityCheckKind.HEADERS, request_json={"method":"GET","path":"/health"}, expected_json={"required_headers":{"x-request-id":None}}, description="Core response tracing/security header baseline."),
    ]
    for payload in rows:
        if payload["case_key"] not in existing:
            db.add(SecurityTestCase(organization_id=actor.organization_id, enabled=True, critical=True, metadata_json={}, **payload))


async def list_scenarios(db: AsyncSession, actor: ActorContext) -> list[PerformanceScenario]:
    _require_manager(actor)
    await get_or_create_pipeline(db, actor)
    return list((await db.scalars(select(PerformanceScenario).where(PerformanceScenario.organization_id == actor.organization_id).order_by(PerformanceScenario.scenario_key))).all())


async def list_security_cases(db: AsyncSession, actor: ActorContext) -> list[SecurityTestCase]:
    _require_manager(actor)
    await get_or_create_pipeline(db, actor)
    return list((await db.scalars(select(SecurityTestCase).where(SecurityTestCase.organization_id == actor.organization_id).order_by(SecurityTestCase.case_key))).all())


async def create_release_run(db: AsyncSession, actor: ActorContext, *, build_ref: str | None, commit_ref: str | None, environment: str) -> ReleaseRun:
    _require_manager(actor)
    pipeline = await get_or_create_pipeline(db, actor)
    row = ReleaseRun(
        organization_id=actor.organization_id,
        pipeline_id=pipeline.id,
        requested_by_membership_id=actor.membership_id,
        status=ReleaseRunStatus.RUNNING,
        app_version=APP_VERSION,
        build_ref=build_ref,
        commit_ref=commit_ref,
        environment=environment,
        started_at=utcnow(),
        summary_json={},
    )
    db.add(row)
    await db.flush()
    stages = [
        ("backend-tests", ReleaseStageKind.BACKEND_TESTS),
        ("legal-qa", ReleaseStageKind.LEGAL_QA),
        ("migrations", ReleaseStageKind.MIGRATIONS),
        ("frontend-static", ReleaseStageKind.FRONTEND_STATIC),
        ("load", ReleaseStageKind.LOAD),
        ("security", ReleaseStageKind.SECURITY),
        ("artifact", ReleaseStageKind.ARTIFACT),
        ("rollback", ReleaseStageKind.ROLLBACK),
    ]
    for stage_key, kind in stages:
        db.add(ReleaseStageRun(release_run_id=row.id, stage_key=stage_key, kind=kind, status=ReleaseStageStatus.PENDING, details_json={}))
    await _audit(db, actor, "release.run.create", "release_run", row.id, {"build_ref": build_ref, "environment": environment})
    await db.commit()
    await db.refresh(row)
    return row


async def _get_run(db: AsyncSession, actor: ActorContext, run_id: UUID) -> ReleaseRun:
    _require_manager(actor)
    row = await db.get(ReleaseRun, run_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Release run not found")
    return row


async def record_stage_result(db: AsyncSession, actor: ActorContext, run_id: UUID, stage_key: str, *, status: str, duration_ms: int, details_json: dict, error: str | None) -> ReleaseStageRun:
    run = await _get_run(db, actor, run_id)
    stage = await db.scalar(select(ReleaseStageRun).where(ReleaseStageRun.release_run_id == run.id, ReleaseStageRun.stage_key == stage_key))
    if not stage:
        raise HTTPException(404, "Release stage not found")
    stage.status = ReleaseStageStatus(status)
    stage.duration_ms = duration_ms
    stage.details_json = details_json
    stage.error = error
    stage.finished_at = utcnow()
    mapping = {
        "backend-tests": None,
        "legal-qa": "qa_passed",
        "migrations": "migration_passed",
        "frontend-static": "frontend_passed",
        "load": "load_passed",
        "security": "security_passed",
    }
    attr = mapping.get(stage_key)
    if attr:
        setattr(run, attr, status == "passed")
    await _audit(db, actor, "release.stage.result", "release_stage", stage.id, {"stage_key": stage_key, "status": status})
    await db.commit()
    await db.refresh(stage)
    return stage


async def submit_performance_result(db: AsyncSession, actor: ActorContext, run_id: UUID, *, scenario_id: UUID, latencies_ms: list[float], success_count: int, failure_count: int, duration_seconds: float, details_json: dict) -> PerformanceRun:
    run = await _get_run(db, actor, run_id)
    scenario = await db.get(PerformanceScenario, scenario_id)
    if not scenario or scenario.organization_id != actor.organization_id:
        raise HTTPException(404, "Performance scenario not found")
    metrics = summarize_latencies(latencies_ms, success_count=success_count, failure_count=failure_count, duration_seconds=duration_seconds)
    passed, reasons = evaluate_performance(metrics, max_p95_ms=scenario.max_p95_ms, min_success_rate=scenario.min_success_rate, max_error_rate=scenario.max_error_rate)
    payload = {**details_json, "thresholds": {"max_p95_ms": scenario.max_p95_ms, "min_success_rate": scenario.min_success_rate, "max_error_rate": scenario.max_error_rate}, "reasons": reasons, "success_rate": metrics["success_rate"]}
    now = utcnow()
    row = PerformanceRun(
        organization_id=actor.organization_id,
        release_run_id=run.id,
        scenario_id=scenario.id,
        status=PerformanceRunStatus.PASSED if passed else PerformanceRunStatus.FAILED,
        started_at=now,
        finished_at=now,
        total_requests=metrics["total_requests"], successful_requests=metrics["successful_requests"], failed_requests=metrics["failed_requests"],
        requests_per_second=metrics["requests_per_second"], p50_ms=metrics["p50_ms"], p95_ms=metrics["p95_ms"], p99_ms=metrics["p99_ms"], max_ms=metrics["max_ms"], error_rate=metrics["error_rate"],
        result_json=payload,
        snapshot_hash=canonical_hash({"scenario": scenario.scenario_key, "metrics": metrics, "passed": passed}),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def submit_security_result(db: AsyncSession, actor: ActorContext, run_id: UUID, *, case_id: UUID, actual_json: dict, error: str | None) -> SecurityTestRun:
    run = await _get_run(db, actor, run_id)
    case = await db.get(SecurityTestCase, case_id)
    if not case or case.organization_id != actor.organization_id:
        raise HTTPException(404, "Security test case not found")
    passed, reasons = evaluate_security_result(actual_json, case.expected_json)
    if error:
        passed = False
        reasons.append(error)
    now = utcnow()
    row = SecurityTestRun(
        organization_id=actor.organization_id,
        release_run_id=run.id,
        case_id=case.id,
        status=SecurityRunStatus.PASSED if passed else SecurityRunStatus.FAILED,
        started_at=now,
        finished_at=now,
        actual_json=actual_json,
        details_json={"reasons": reasons, "critical": case.critical},
        error=error,
        snapshot_hash=canonical_hash({"case": case.case_key, "actual": actual_json, "passed": passed}),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def register_artifact(db: AsyncSession, actor: ActorContext, run_id: UUID, *, kind: str, filename: str, sha256: str, size_bytes: int, storage_path: str | None, metadata_json: dict) -> ReleaseArtifact:
    run = await _get_run(db, actor, run_id)
    try:
        artifact_kind = ReleaseArtifactKind(kind)
    except ValueError:
        artifact_kind = ReleaseArtifactKind.OTHER
    row = ReleaseArtifact(
        release_run_id=run.id,
        kind=artifact_kind,
        filename=filename,
        storage_path=storage_path,
        sha256=sha256.casefold(),
        size_bytes=size_bytes,
        metadata_json=metadata_json,
    )
    db.add(row)
    await db.flush()
    await _audit(db, actor, "release.artifact.register", "release_artifact", row.id, {"filename": filename, "sha256": sha256.casefold()})
    await db.commit()
    await db.refresh(row)
    return row


async def create_rollback_point(db: AsyncSession, actor: ActorContext, run_id: UUID, *, database_revision: str | None, release_artifact_id: UUID | None, backup_run_id: UUID | None, notes: str | None, verified: bool) -> RollbackPoint:
    run = await _get_run(db, actor, run_id)
    row = RollbackPoint(
        organization_id=actor.organization_id,
        release_run_id=run.id,
        app_version=run.app_version,
        database_revision=database_revision,
        release_artifact_id=release_artifact_id,
        backup_run_id=backup_run_id,
        status=RollbackPointStatus.READY if verified else RollbackPointStatus.INVALID,
        verified_at=utcnow() if verified else None,
        notes=notes,
        metadata_json={"verification_only": True},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def evaluate_release(db: AsyncSession, actor: ActorContext, run_id: UUID) -> dict:
    run = await _get_run(db, actor, run_id)
    pipeline = await db.get(ReleasePipeline, run.pipeline_id)
    stages = list((await db.scalars(select(ReleaseStageRun).where(ReleaseStageRun.release_run_id == run.id))).all())
    stage_map = {s.stage_key: _enum_value(s.status) for s in stages}
    perf = list((await db.scalars(select(PerformanceRun).where(PerformanceRun.release_run_id == run.id))).all())
    security = list((await db.scalars(select(SecurityTestRun).where(SecurityTestRun.release_run_id == run.id))).all())
    security_cases = {c.id: c for c in (await db.scalars(select(SecurityTestCase).where(SecurityTestCase.organization_id == actor.organization_id))).all()}
    critical_security_failures = sum(1 for s in security if _enum_value(s.status) != SecurityRunStatus.PASSED.value and security_cases.get(s.case_id) and security_cases[s.case_id].critical)
    rollback_ready = bool(await db.scalar(select(func.count()).select_from(RollbackPoint).where(RollbackPoint.release_run_id == run.id, RollbackPoint.status == RollbackPointStatus.READY)))
    artifact_passed = stage_map.get("artifact") == "passed"

    # Stage results are the source of truth for CI-driven release runs. The QA database gate can
    # additionally be linked by the caller in details, but absence never silently passes the gate.
    backend_tests_passed = stage_map.get("backend-tests") == "passed"
    qa_passed = run.qa_passed if run.qa_passed is not None else (stage_map.get("legal-qa") == "passed")
    security_passed = run.security_passed if run.security_passed is not None else (bool(security) and all(_enum_value(s.status) == "passed" for s in security))
    load_passed = run.load_passed if run.load_passed is not None else (bool(perf) and all(_enum_value(p.status) == "passed" for p in perf))
    migration_passed = run.migration_passed if run.migration_passed is not None else (stage_map.get("migrations") == "passed")
    frontend_passed = run.frontend_passed if run.frontend_passed is not None else (stage_map.get("frontend-static") == "passed")
    gate_input = ReleaseGateInput(
        backend_tests_passed=backend_tests_passed,
        qa_passed=qa_passed,
        security_passed=security_passed,
        load_passed=load_passed,
        migration_passed=migration_passed,
        frontend_passed=frontend_passed,
        critical_security_failures=critical_security_failures,
        rollback_ready=rollback_ready,
        artifact_passed=artifact_passed,
    )
    passed, reasons = decide_release_gate(
        gate_input,
        require_qa_gate=pipeline.require_qa_gate,
        require_security_zero_critical=pipeline.require_security_zero_critical,
        require_migration_roundtrip=pipeline.require_migration_roundtrip,
        require_frontend_static=pipeline.require_frontend_static,
        require_load_gate=pipeline.require_load_gate,
        require_rollback_point=True,
    )
    summary = {
        "passed": passed,
        "reasons": reasons,
        "critical_security_failures": critical_security_failures,
        "stage_status": stage_map,
        "performance_runs": len(perf),
        "security_runs": len(security),
        "rollback_ready": rollback_ready,
        "artifact_passed": artifact_passed,
    }
    run.status = ReleaseRunStatus.PASSED if passed else ReleaseRunStatus.HELD
    run.finished_at = utcnow()
    run.summary_json = summary
    run.snapshot_hash = canonical_hash({"run": str(run.id), "version": run.app_version, **summary})
    await _audit(db, actor, "release.run.evaluate", "release_run", run.id, {"passed": passed, "reasons": reasons})
    await db.commit()
    return summary


async def approve_release(db: AsyncSession, actor: ActorContext, run_id: UUID, *, decision: str, note: str | None) -> DeploymentApproval:
    run = await _get_run(db, actor, run_id)
    if decision == DeploymentDecision.APPROVE.value and _enum_value(run.status) not in {ReleaseRunStatus.PASSED.value, ReleaseRunStatus.APPROVED.value}:
        raise HTTPException(409, "Release gate must pass before deployment approval")
    existing = await db.scalar(select(DeploymentApproval).where(DeploymentApproval.release_run_id == run.id, DeploymentApproval.membership_id == actor.membership_id))
    if existing:
        existing.decision = DeploymentDecision(decision)
        existing.note = note
        existing.decided_at = utcnow()
        row = existing
    else:
        row = DeploymentApproval(release_run_id=run.id, membership_id=actor.membership_id, decision=DeploymentDecision(decision), note=note, decided_at=utcnow())
        db.add(row)
    run.status = ReleaseRunStatus.APPROVED if decision == "approve" else ReleaseRunStatus.REJECTED
    await _audit(db, actor, "release.deployment.decision", "release_run", run.id, {"decision": decision})
    await db.commit()
    await db.refresh(row)
    return row


async def release_detail(db: AsyncSession, actor: ActorContext, run_id: UUID) -> dict:
    run = await _get_run(db, actor, run_id)
    stages = list((await db.scalars(select(ReleaseStageRun).where(ReleaseStageRun.release_run_id == run.id).order_by(ReleaseStageRun.created_at))).all())
    performance = list((await db.scalars(select(PerformanceRun).where(PerformanceRun.release_run_id == run.id).order_by(PerformanceRun.created_at))).all())
    security = list((await db.scalars(select(SecurityTestRun).where(SecurityTestRun.release_run_id == run.id).order_by(SecurityTestRun.created_at))).all())
    artifacts = list((await db.scalars(select(ReleaseArtifact).where(ReleaseArtifact.release_run_id == run.id).order_by(ReleaseArtifact.created_at))).all())
    rollbacks = list((await db.scalars(select(RollbackPoint).where(RollbackPoint.release_run_id == run.id).order_by(RollbackPoint.created_at))).all())
    approvals = list((await db.scalars(select(DeploymentApproval).where(DeploymentApproval.release_run_id == run.id).order_by(DeploymentApproval.decided_at))).all())
    gate = run.summary_json if run.summary_json else {"passed": False, "reasons": ["release has not been evaluated"]}
    return {"run": run, "stages": stages, "performance": performance, "security": security, "artifacts": artifacts, "rollback_points": rollbacks, "approvals": approvals, "gate": gate}


async def list_runs(db: AsyncSession, actor: ActorContext, *, limit: int = 30) -> list[ReleaseRun]:
    _require_manager(actor)
    return list((await db.scalars(select(ReleaseRun).where(ReleaseRun.organization_id == actor.organization_id).order_by(ReleaseRun.created_at.desc()).limit(limit))).all())


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    pipeline = await get_or_create_pipeline(db, actor)
    runs = await list_runs(db, actor, limit=12)
    scenarios = await list_scenarios(db, actor)
    cases = await list_security_cases(db, actor)
    latest = runs[0] if runs else None
    summary = {
        "app_version": APP_VERSION,
        "latest_status": _enum_value(latest.status) if latest else "not_run",
        "latest_gate_passed": bool(latest and latest.summary_json.get("passed")),
        "release_runs": len(runs),
        "performance_scenarios": len(scenarios),
        "security_cases": len(cases),
        "critical_security_cases": sum(1 for case in cases if case.critical),
    }
    return {"pipeline": pipeline, "latest_runs": runs, "performance_scenarios": scenarios, "security_cases": cases, "summary": summary}
