from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa import (
    EvaluationBaseline,
    EvaluationCase,
    EvaluationCaseRun,
    EvaluationCaseRunStatus,
    EvaluationCaseStatus,
    EvaluationCategory,
    EvaluationMetric,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationSuite,
    QAFinding,
    QAFindingSeverity,
    ReleaseQualityGate,
    ReleaseQualityGateRun,
)
from app.services.qa.evaluators import canonical_hash, category_scores, evaluate_probe, evaluate_release_gate
from app.services.security.context import ActorContext

APP_VERSION = "0.29.0-rc.1"
MANAGER_ROLES = {"owner", "admin", "partner"}


def _manager(actor: ActorContext) -> None:
    if actor.role.value not in MANAGER_ROLES:
        raise HTTPException(403, "Firm manager role required")


def _value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _severity(critical: bool, category: str) -> QAFindingSeverity:
    if critical or category in {"security", "citation"}:
        return QAFindingSeverity.CRITICAL
    return QAFindingSeverity.HIGH


DEFAULT_CASES: list[dict] = [
    {
        "case_key": "language.section.hindi",
        "title": "Hindi section reference normalizes to canonical section",
        "category": "language",
        "evaluator": "language_normalization",
        "critical": True,
        "input_json": {"text": "धारा 420 के अंतर्गत आवेदन"},
        "expected_json": {"references": ["section:420"], "normalized_contains": ["section 420"]},
        "tags_json": ["hindi", "legal-reference"],
    },
    {
        "case_key": "language.section.hinglish",
        "title": "Hinglish dhara reference normalizes to canonical section",
        "category": "language",
        "evaluator": "language_normalization",
        "input_json": {"text": "dhara 138 cheque notice"},
        "expected_json": {"references": ["section:138"], "normalized_contains": ["section 138"]},
        "tags_json": ["hinglish", "legal-reference"],
    },
    {
        "case_key": "citation.insc",
        "title": "INSC citation parser remains stable",
        "category": "citation",
        "evaluator": "citation_parser",
        "critical": True,
        "input_json": {"text": "See 2024 INSC 321 for the proposition."},
        "expected_json": {"citations": ["2024 INSC 321"], "reject_extra": True},
    },
    {
        "case_key": "citation.scc",
        "title": "SCC citation parser remains stable",
        "category": "citation",
        "evaluator": "citation_parser",
        "critical": True,
        "input_json": {"text": "The case is reported at (2024) 5 SCC 123."},
        "expected_json": {"citations": ["(2024) 5 SCC 123"], "reject_extra": True},
    },
    {
        "case_key": "deadline.calendar",
        "title": "Calendar-day deadline calculation is deterministic",
        "category": "deadline",
        "evaluator": "deadline_calculator",
        "critical": True,
        "input_json": {"trigger_date": "2026-08-08", "offset_days": 7, "day_basis": "calendar", "count_from_next_day": True, "adjustment": "none"},
        "expected_json": {"due_date": "2026-08-15"},
    },
    {
        "case_key": "deadline.business.holiday",
        "title": "Business-day deadline skips weekend and supplied holiday",
        "category": "deadline",
        "evaluator": "deadline_calculator",
        "input_json": {"trigger_date": "2026-08-07", "offset_days": 2, "day_basis": "business", "count_from_next_day": True, "adjustment": "none", "holidays": ["2026-08-10"]},
        "expected_json": {"due_date": "2026-08-12"},
    },
    {
        "case_key": "evidence.hindi.financial",
        "title": "Hindi financial evidence classification remains stable",
        "category": "evidence",
        "evaluator": "evidence_classifier",
        "input_json": {"filename": "रसीद.pdf", "text": "भुगतान की रसीद और बैंक विवरण"},
        "expected_json": {"kind": "financial"},
    },
    {
        "case_key": "evidence.english.contract",
        "title": "English agreement is classified as contract evidence",
        "category": "evidence",
        "evaluator": "evidence_classifier",
        "input_json": {"filename": "agreement.pdf", "text": "This Services Agreement is made between the parties."},
        "expected_json": {"kind": "contract"},
    },
    {
        "case_key": "security.ethical_wall_no_leak",
        "title": "Restricted client/matter identifiers never appear in permitted result payload",
        "category": "security",
        "evaluator": "forbidden_absent",
        "critical": True,
        "input_json": {"actual": "Search results: public statute; permitted matter ABC"},
        "expected_json": {"values": ["Secret Acquisition Client XYZ", "Restricted Matter 42"]},
    },
    {
        "case_key": "drafting.provenance",
        "title": "Draft substantive claims retain source provenance",
        "category": "drafting",
        "evaluator": "provenance_complete",
        "critical": True,
        "input_json": {"claims": [{"text": "Agreement executed on 12 March", "source_ids": ["S1"]}, {"text": "Payment made", "source_ids": ["S2"]}]},
        "expected_json": {"min_coverage": 1.0},
    },
    {
        "case_key": "search.relevance.top3",
        "title": "Relevant authority remains within top three search results",
        "category": "search",
        "evaluator": "rank_at_k",
        "input_json": {"ranked_ids": ["authority-1", "authority-2", "authority-3"]},
        "expected_json": {"relevant_ids": ["authority-1"], "k": 3, "min_recall": 1.0},
    },
    {
        "case_key": "ocr.hindi.token_recall",
        "title": "Captured Hindi OCR golden text meets token-recall floor",
        "category": "ocr",
        "evaluator": "ocr_text_quality",
        "input_json": {"ocr_text": "न्यायालय में याचिकाकर्ता ने आवेदन प्रस्तुत किया"},
        "expected_json": {"text": "न्यायालय में याचिकाकर्ता ने आवेदन प्रस्तुत किया", "min_token_recall": 0.95},
        "source_note": "Representative captured OCR output; replace/add scanned golden files for production benchmarking.",
    },
    {
        "case_key": "case_lookup.cnr.exact",
        "title": "Exact CNR input is detected without ambiguous case-number parsing",
        "category": "case_lookup",
        "evaluator": "case_query_parser",
        "critical": True,
        "input_json": {"query": "UPLU010012342024"},
        "expected_json": {"parsed": {"kind": "cnr", "cnr": "UPLU010012342024"}},
        "tags_json": ["case-lookup", "cnr"],
    },
    {
        "case_key": "case_lookup.number.type.year",
        "title": "Case type, number and year are parsed deterministically",
        "category": "case_lookup",
        "evaluator": "case_query_parser",
        "input_json": {"query": "CS 234/2025"},
        "expected_json": {"parsed": {"kind": "case_number", "case_type": "CS", "case_number": "234", "year": 2025}},
        "tags_json": ["case-lookup", "resolver"],
    },
    {
        "case_key": "case_lookup.number.hindi_type",
        "title": "Hindi case-type text is parsed without guessing a court abbreviation",
        "category": "case_lookup",
        "evaluator": "case_query_parser",
        "input_json": {"query": "सिविल वाद 234/2025"},
        "expected_json": {"parsed": {"kind": "case_number", "case_type": "सिविल वाद", "case_number": "234", "year": 2025}},
        "tags_json": ["case-lookup", "hindi"],
    },
    {
        "case_key": "remedy.verified_trigger.deadline",
        "title": "Remedy rule uses an explicit order trigger and deterministic deadline arithmetic",
        "category": "remedy",
        "evaluator": "remedy_rule",
        "critical": True,
        "input_json": {
            "as_of_date": "2026-08-08",
            "context": {
                "case_stage": "Final judgment",
                "status": "Disposed",
                "court_level": "District Court",
                "orders": [{"order_date": "2026-08-01", "order_type": "final order"}],
                "judgments": [],
                "acts": []
            },
            "rule": {
                "case_stage_patterns_json": ["final"],
                "requires_latest_order": True,
                "maintainability_json": {"requirements": [{"field": "latest_order", "operator": "exists"}]},
                "limitation_json": {"days": 30, "trigger": "latest_order_date", "day_basis": "calendar", "count_from_next_day": True, "requires_lawyer_review": True},
                "priority": 70
            }
        },
        "expected_json": {"matched": True, "status": "possible", "due_date": "2026-08-31"},
        "tags_json": ["remedy", "deadline", "maintainability"],
        "source_note": "Arithmetic fixture only; it is not a bundled substantive limitation rule."
    },
    {
        "case_key": "contract.review.shape",
        "title": "Contract review output retains required deterministic fields",
        "category": "contract",
        "evaluator": "json_contract",
        "input_json": {"actual": {"health_score": 88, "findings": [], "clauses": []}},
        "expected_json": {"required_keys": ["health_score", "findings", "clauses"]},
    },
]


async def seed_default_suite(db: AsyncSession, actor: ActorContext) -> EvaluationSuite:
    _manager(actor)
    existing = await db.scalar(select(EvaluationSuite).where(EvaluationSuite.organization_id == actor.organization_id, EvaluationSuite.suite_key == "core-release"))
    if existing:
        return existing
    suite = EvaluationSuite(
        organization_id=actor.organization_id,
        suite_key="core-release",
        name="Core legal release gate",
        description="Deterministic golden cases for bilingual legal accuracy, security, citations, deadlines and provenance.",
        version=1,
        enabled=True,
        default_gate=True,
        tags_json=["release", "golden", "bilingual"],
        metadata_json={"seeded_by": "batch22"},
    )
    db.add(suite)
    await db.flush()
    for payload in DEFAULT_CASES:
        source_hash = canonical_hash({"input": payload.get("input_json", {}), "expected": payload.get("expected_json", {})})
        db.add(EvaluationCase(suite_id=suite.id, source_hash=source_hash, **payload))
    gate = ReleaseQualityGate(
        organization_id=actor.organization_id,
        name="Default release quality gate",
        enabled=True,
        min_overall_score=0.95,
        max_critical_failures=0,
        require_security_zero_failures=True,
        require_citation_zero_failures=True,
        category_thresholds_json={"security": 1.0, "citation": 1.0, "deadline": 1.0, "language": 1.0, "drafting": 1.0, "case_lookup": 1.0, "remedy": 1.0},
        metadata_json={"seeded_by": "batch22"},
    )
    db.add(gate)
    await db.commit()
    await db.refresh(suite)
    return suite


async def list_suites(db: AsyncSession, actor: ActorContext) -> list[EvaluationSuite]:
    return list((await db.scalars(select(EvaluationSuite).where(EvaluationSuite.organization_id == actor.organization_id).order_by(EvaluationSuite.name))).all())


async def suite_detail(db: AsyncSession, actor: ActorContext, suite_id: UUID) -> dict:
    suite = await db.scalar(select(EvaluationSuite).where(EvaluationSuite.id == suite_id, EvaluationSuite.organization_id == actor.organization_id))
    if not suite:
        raise HTTPException(404, "Evaluation suite not found")
    cases = list((await db.scalars(select(EvaluationCase).where(EvaluationCase.suite_id == suite.id).order_by(EvaluationCase.category, EvaluationCase.case_key))).all())
    return {"suite": suite, "cases": cases}


async def add_case(db: AsyncSession, actor: ActorContext, suite_id: UUID, payload: dict) -> EvaluationCase:
    _manager(actor)
    await suite_detail(db, actor, suite_id)
    try:
        category = EvaluationCategory(payload["category"])
    except ValueError as exc:
        raise HTTPException(422, f"Unsupported category: {payload['category']}") from exc
    row = EvaluationCase(
        suite_id=suite_id,
        category=category,
        source_hash=canonical_hash({"input": payload.get("input_json", {}), "expected": payload.get("expected_json", {})}),
        **{k: v for k, v in payload.items() if k != "category"},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_or_create_gate(db: AsyncSession, actor: ActorContext) -> ReleaseQualityGate:
    gate = await db.scalar(select(ReleaseQualityGate).where(ReleaseQualityGate.organization_id == actor.organization_id).order_by(desc(ReleaseQualityGate.created_at)))
    if gate:
        return gate
    _manager(actor)
    gate = ReleaseQualityGate(organization_id=actor.organization_id, name="Default release quality gate")
    db.add(gate)
    await db.commit()
    await db.refresh(gate)
    return gate


async def update_gate(db: AsyncSession, actor: ActorContext, payload: dict) -> ReleaseQualityGate:
    _manager(actor)
    gate = await get_or_create_gate(db, actor)
    for key, value in payload.items():
        if value is not None:
            setattr(gate, key, value)
    await db.commit()
    await db.refresh(gate)
    return gate


async def run_suite(db: AsyncSession, actor: ActorContext, suite_id: UUID, *, trigger: str = "manual", build_ref: str | None = None) -> EvaluationRun:
    _manager(actor)
    detail = await suite_detail(db, actor, suite_id)
    suite = detail["suite"]
    cases = [case for case in detail["cases"] if case.status == EvaluationCaseStatus.ACTIVE]
    started_wall = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    run = EvaluationRun(
        organization_id=actor.organization_id,
        suite_id=suite.id,
        requested_by_membership_id=actor.membership_id,
        status=EvaluationRunStatus.RUNNING,
        trigger=trigger,
        app_version=APP_VERSION,
        build_ref=build_ref,
        started_at=started_wall,
        total_cases=len(cases),
    )
    db.add(run)
    await db.flush()

    scored: list[dict] = []
    passed_cases = 0
    failed_cases = 0
    critical_failures = 0

    for case in cases:
        try:
            outcome = evaluate_probe(case.evaluator, dict(case.input_json or {}), dict(case.expected_json or {}))
            status = EvaluationCaseRunStatus.PASSED if outcome.passed else EvaluationCaseRunStatus.FAILED
            case_run = EvaluationCaseRun(
                run_id=run.id,
                case_id=case.id,
                status=status,
                score=outcome.score,
                duration_ms=outcome.duration_ms,
                actual_json=outcome.actual,
                expected_json=case.expected_json or {},
                details_json=outcome.details,
            )
            db.add(case_run)
            await db.flush()
            if outcome.passed:
                passed_cases += 1
            else:
                failed_cases += 1
                if case.critical:
                    critical_failures += 1
                db.add(QAFinding(
                    organization_id=actor.organization_id,
                    run_id=run.id,
                    case_run_id=case_run.id,
                    category=_value(case.category),
                    severity=_severity(case.critical, _value(case.category)),
                    code="GOLDEN_CASE_FAILED",
                    message=f"Golden case failed: {case.title}",
                    details_json={"case_key": case.case_key, "details": outcome.details},
                ))
            for finding in outcome.findings:
                db.add(QAFinding(
                    organization_id=actor.organization_id,
                    run_id=run.id,
                    case_run_id=case_run.id,
                    category=_value(case.category),
                    severity=QAFindingSeverity(finding.get("severity", "warning")),
                    code=str(finding.get("code", "EVALUATION_FINDING")),
                    message=str(finding.get("message", "Evaluation finding")),
                    details_json={k: v for k, v in finding.items() if k not in {"severity", "code", "message"}},
                ))
            scored.append({"category": _value(case.category), "score": outcome.score, "weight": case.weight})
        except Exception as exc:  # QA must record evaluator errors instead of aborting the entire release run.
            failed_cases += 1
            if case.critical:
                critical_failures += 1
            case_run = EvaluationCaseRun(
                run_id=run.id,
                case_id=case.id,
                status=EvaluationCaseRunStatus.ERROR,
                score=0.0,
                expected_json=case.expected_json or {},
                error=f"{type(exc).__name__}: {exc}",
            )
            db.add(case_run)
            await db.flush()
            db.add(QAFinding(
                organization_id=actor.organization_id,
                run_id=run.id,
                case_run_id=case_run.id,
                category=_value(case.category),
                severity=QAFindingSeverity.CRITICAL if case.critical else QAFindingSeverity.HIGH,
                code="EVALUATOR_ERROR",
                message=f"Evaluator error in {case.case_key}",
                details_json={"error": case_run.error},
            ))
            scored.append({"category": _value(case.category), "score": 0.0, "weight": case.weight})

    cat_scores = category_scores(scored)
    total_weight = sum(max(0.0, row["weight"]) for row in scored)
    overall = 1.0 if not scored else (sum(row["score"] * max(0.0, row["weight"]) for row in scored) / max(total_weight, 1e-9))
    for category, score in cat_scores.items():
        db.add(EvaluationMetric(run_id=run.id, category=category, metric_key=f"category.{category}.score", value=score, details_json={"scale": "0-1"}))
    db.add(EvaluationMetric(run_id=run.id, category="overall", metric_key="overall.score", value=overall, details_json={"scale": "0-1"}))

    gate = await get_or_create_gate(db, actor)
    gate_passed, reasons = evaluate_release_gate(
        overall_score=overall,
        critical_failures=critical_failures,
        category_scores_map=cat_scores,
        gate={
            "min_overall_score": gate.min_overall_score,
            "max_critical_failures": gate.max_critical_failures,
            "require_security_zero_failures": gate.require_security_zero_failures,
            "require_citation_zero_failures": gate.require_citation_zero_failures,
            "category_thresholds_json": gate.category_thresholds_json or {},
        },
    )
    finished = datetime.now(timezone.utc)
    run.status = EvaluationRunStatus.PASSED if gate_passed else EvaluationRunStatus.FAILED
    run.finished_at = finished
    run.passed_cases = passed_cases
    run.failed_cases = failed_cases
    run.critical_failures = critical_failures
    run.overall_score = round(overall, 6)
    run.duration_ms = max(0, round((time.perf_counter() - started_perf) * 1000))
    run.summary_json = {"category_scores": cat_scores, "release_gate_passed": gate_passed, "release_gate_reasons": reasons}
    run.snapshot_hash = canonical_hash({
        "suite": suite.suite_key,
        "version": suite.version,
        "app_version": APP_VERSION,
        "build_ref": build_ref,
        "overall_score": run.overall_score,
        "category_scores": cat_scores,
        "cases": [{"case_key": c.case_key, "source_hash": c.source_hash} for c in cases],
        "gate_passed": gate_passed,
        "reasons": reasons,
    })
    gate_hash = canonical_hash({"run_hash": run.snapshot_hash, "gate_id": str(gate.id), "passed": gate_passed, "reasons": reasons, "category_scores": cat_scores})
    db.add(ReleaseQualityGateRun(gate_id=gate.id, evaluation_run_id=run.id, passed=gate_passed, evaluated_at=finished, reasons_json=reasons, category_scores_json=cat_scores, snapshot_hash=gate_hash))
    await db.commit()
    await db.refresh(run)
    return run


async def list_runs(db: AsyncSession, actor: ActorContext, limit: int = 30) -> list[EvaluationRun]:
    return list((await db.scalars(select(EvaluationRun).where(EvaluationRun.organization_id == actor.organization_id).order_by(desc(EvaluationRun.created_at)).limit(limit))).all())


async def run_detail(db: AsyncSession, actor: ActorContext, run_id: UUID) -> dict:
    run = await db.scalar(select(EvaluationRun).where(EvaluationRun.id == run_id, EvaluationRun.organization_id == actor.organization_id))
    if not run:
        raise HTTPException(404, "Evaluation run not found")
    case_runs = list((await db.scalars(select(EvaluationCaseRun).where(EvaluationCaseRun.run_id == run.id).order_by(EvaluationCaseRun.created_at))).all())
    findings = list((await db.scalars(select(QAFinding).where(QAFinding.run_id == run.id).order_by(QAFinding.severity.desc(), QAFinding.created_at))).all())
    metrics = list((await db.scalars(select(EvaluationMetric).where(EvaluationMetric.run_id == run.id).order_by(EvaluationMetric.metric_key))).all())
    gate_run = await db.scalar(select(ReleaseQualityGateRun).where(ReleaseQualityGateRun.evaluation_run_id == run.id).order_by(desc(ReleaseQualityGateRun.created_at)))
    gate = None
    if gate_run:
        gate = {"passed": gate_run.passed, "reasons": gate_run.reasons_json, "category_scores": gate_run.category_scores_json, "snapshot_hash": gate_run.snapshot_hash, "evaluated_at": gate_run.evaluated_at}
    return {"run": run, "case_runs": case_runs, "findings": findings, "metrics": metrics, "gate": gate}


async def create_baseline(db: AsyncSession, actor: ActorContext, run_id: UUID, name: str) -> EvaluationBaseline:
    _manager(actor)
    detail = await run_detail(db, actor, run_id)
    run: EvaluationRun = detail["run"]
    if run.status != EvaluationRunStatus.PASSED:
        raise HTTPException(409, "Only a gate-passing evaluation run can become a baseline")
    metrics = {row.metric_key: row.value for row in detail["metrics"]}
    row = EvaluationBaseline(
        organization_id=actor.organization_id,
        suite_id=run.suite_id,
        run_id=run.id,
        approved_by_membership_id=actor.membership_id,
        name=name,
        metrics_json=metrics,
        approved_at=datetime.now(timezone.utc),
        snapshot_hash=canonical_hash({"run_hash": run.snapshot_hash, "name": name, "metrics": metrics}),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    suites = await list_suites(db, actor)
    latest_runs = await list_runs(db, actor, limit=12)
    gate = await db.scalar(select(ReleaseQualityGate).where(ReleaseQualityGate.organization_id == actor.organization_id).order_by(desc(ReleaseQualityGate.created_at)))
    latest_gate = None
    if latest_runs:
        gate_run = await db.scalar(select(ReleaseQualityGateRun).where(ReleaseQualityGateRun.evaluation_run_id == latest_runs[0].id).order_by(desc(ReleaseQualityGateRun.created_at)))
        if gate_run:
            latest_gate = {"passed": gate_run.passed, "reasons": gate_run.reasons_json, "category_scores": gate_run.category_scores_json, "snapshot_hash": gate_run.snapshot_hash}
    latest = latest_runs[0] if latest_runs else None
    return {
        "suites": suites,
        "latest_runs": latest_runs,
        "default_gate": gate,
        "latest_gate_result": latest_gate,
        "summary": {
            "suite_count": len(suites),
            "latest_status": _value(latest.status) if latest else "not_run",
            "latest_score": latest.overall_score if latest else None,
            "critical_failures": latest.critical_failures if latest else 0,
            "release_ready": bool(latest_gate and latest_gate.get("passed")),
        },
    }
