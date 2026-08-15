"""The agent executor.

Runs a recipe's steps in order against one matter and stops. Nothing here
writes to the matter, files anything, or sends anything — a completed run sits
at AWAITING_APPROVAL until a lawyer accepts or rejects it. That boundary is the
point of the design, not a limitation of it.

Two rules keep the output honest:

* A deterministic step calls a rule engine and either produces a result or
  fails. It never guesses.
* An AI step is *skipped*, not failed, when no provider is configured, and the
  run records that it was skipped. A report missing its AI half says so rather
  than reading as complete.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from string import Template
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import (
    AgentRecipe,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepKind,
    AgentStepStatus,
)
from app.schemas.ai import AIReasoningRequest
from app.services import matters as matters_service
from app.services.agent import memory as memory_service
from app.services.agent.recipes import RECIPES, RecipeSpec, StepSpec, get_recipe
from app.services.ai import service as ai_service
from app.services.documents import service as documents_service
from app.services.intelligence import service as intelligence_service
from app.services.procedure import service as procedure_service


async def _ai_available() -> bool:
    status = await ai_service.provider_status()
    return bool(status.get("local_enabled") or status.get("remote_enabled"))


# --- deterministic steps ----------------------------------------------------
#
# Each returns the dict stored on the step. Shapes are per-step and rendered by
# the UI, so they stay close to what a reader needs rather than being forced
# into one envelope.


async def _step_matter_brief(db: AsyncSession, matter_id: UUID) -> dict:
    matter = await matters_service.get_matter(db, matter_id)
    documents = await documents_service.list_documents(db, matter_id)
    return {
        "title": matter.title,
        "case_number": matter.case_number or matter.reference_number,
        "court": matter.court_name or matter.jurisdiction,
        "client": matter.client_name,
        "status": str(matter.status),
        "primary_language": str(matter.primary_language),
        "document_count": len(documents),
        "documents_ready": sum(
            1 for d in documents if str(getattr(d, "processing_status", "")) == "ready"
        ),
    }


async def _step_procedural_history(db: AsyncSession, matter_id: UUID) -> dict:
    timeline = await intelligence_service.list_timeline(db, matter_id)
    events = [
        {
            "on": e.occurred_on.isoformat() if getattr(e, "occurred_on", None) else None,
            "label": getattr(e, "label", "") or getattr(e, "title", ""),
            "kind": str(getattr(e, "event_type", "") or ""),
        }
        for e in timeline
    ]
    return {"event_count": len(events), "events": events[-25:]}


async def _step_limitation(db: AsyncSession, matter_id: UUID) -> dict:
    """Reports the recorded limitation deadlines rather than inferring which
    article applies. Choosing the article is a lawyer's call; the engine only
    does the arithmetic once someone has made it."""
    deadlines = await procedure_service.list_deadlines(db, matter_id=matter_id)
    today = date.today()
    rows = []
    for d in deadlines:
        due = getattr(d, "due_on", None)
        rows.append(
            {
                "label": getattr(d, "label", "") or getattr(d, "title", ""),
                "due_on": due.isoformat() if due else None,
                "days_remaining": (due - today).days if due else None,
                "status": str(procedure_service.deadline_status(d, today)),
            }
        )
    expired = [r for r in rows if r["days_remaining"] is not None and r["days_remaining"] < 0]
    return {
        "deadline_count": len(rows),
        "expired_count": len(expired),
        "deadlines": rows,
        "note": None
        if rows
        else "No limitation or procedural deadline recorded on this matter.",
    }


async def _step_upcoming(db: AsyncSession, matter_id: UUID) -> dict:
    agenda = await procedure_service.agenda(db, matter_id=matter_id, days=14)
    return {
        "window_days": 14,
        "item_count": len(agenda),
        "items": [
            {
                "kind": item.get("kind"),
                "title": item.get("title"),
                "when": str(item.get("when")) if item.get("when") is not None else None,
                "requires_review": bool(item.get("requires_review")),
            }
            for item in agenda
        ],
    }


async def _step_gaps(db: AsyncSession, matter_id: UUID) -> dict:
    contradictions = await intelligence_service.list_contradictions(db, matter_id)
    review_items = await intelligence_service.list_review_items(db, matter_id)
    unresolved = [c for c in contradictions if str(getattr(c, "status", "")) != "resolved"]
    return {
        "unresolved_contradiction_count": len(unresolved),
        "review_item_count": len(review_items),
        "contradictions": [
            {
                "label": getattr(c, "label", ""),
                "severity": str(getattr(c, "severity", "")),
                "explanation": getattr(c, "explanation", None),
            }
            for c in unresolved[:10]
        ],
        "review_items": [
            {"label": getattr(r, "label", "") or getattr(r, "title", "")} for r in review_items[:10]
        ],
    }


_DETERMINISTIC = {
    "matter_brief": _step_matter_brief,
    "procedural_history": _step_procedural_history,
    "limitation": _step_limitation,
    "upcoming": _step_upcoming,
    "gaps": _step_gaps,
}


def _render_query(spec: StepSpec, matter, mem) -> str:
    """Fills the step's prompt template from matter memory.

    safe_substitute rather than substitute: a placeholder the recipe author
    forgot to supply should leave the prompt readable, not raise mid-run.
    """
    issues = ", ".join(str(i.get("label", i)) for i in (mem.issues_json or [])) or "none recorded"
    questions = (
        ", ".join(str(q.get("label", q)) for q in (mem.open_questions_json or []))
        or "none recorded"
    )
    contradictions = (
        ", ".join(
            str(c.get("label", "")) for c in (mem.snapshot_json or {}).get("top_contradictions", [])
        )
        or "none recorded"
    )
    return Template(spec.query_template or "").safe_substitute(
        matter_title=matter.title,
        issues=issues,
        open_questions=questions,
        contradictions=contradictions,
        strategy=mem.strategy_notes or "none recorded",
    )


async def start_run(
    db: AsyncSession,
    matter_id: UUID,
    recipe: AgentRecipe,
    *,
    output_language: str = "en",
) -> AgentRun:
    """Runs every step, then stops for review.

    Steps run inline rather than as a background job: the deterministic half is
    a handful of queries, and a lawyer asking for hearing prep is waiting for
    it. Moving to the jobs queue is the right change once AI steps dominate the
    wall time.
    """
    matter = await matters_service.get_matter(db, matter_id)
    spec: RecipeSpec = get_recipe(recipe)
    ai_on = await _ai_available()

    run = AgentRun(
        matter_id=matter_id,
        recipe=recipe,
        title=spec.title,
        status=AgentRunStatus.RUNNING,
        output_language=output_language,
        ai_available=ai_on,
    )
    db.add(run)
    await db.flush()

    mem = await memory_service.refresh(db, matter_id)

    for ordinal, step_spec in enumerate(spec.steps):
        step = AgentStep(
            run_id=run.id,
            ordinal=ordinal,
            step_key=step_spec.key,
            label=step_spec.label,
            kind=step_spec.kind,
            status=AgentStepStatus.PENDING,
        )
        db.add(step)
        await db.flush()

        try:
            if step_spec.kind is AgentStepKind.DETERMINISTIC:
                handler = _DETERMINISTIC[step_spec.key]
                step.output_json = await handler(db, matter_id)
                step.status = AgentStepStatus.COMPLETED
            elif not ai_on:
                step.status = AgentStepStatus.SKIPPED
                step.note = (
                    "No AI provider is configured, so this step did not run. "
                    "The deterministic steps are unaffected."
                )
            else:
                ai_run = await ai_service.run_reasoning(
                    db,
                    AIReasoningRequest(
                        matter_id=matter_id,
                        task_type=step_spec.task_type,
                        query=_render_query(step_spec, matter, mem),
                        output_language=output_language,
                    ),
                )
                step.ai_run_id = ai_run.id
                step.output_json = {
                    "response_text": ai_run.response_text,
                    "verification_status": str(ai_run.verification_status),
                    "review_status": str(ai_run.review_status),
                }
                step.status = AgentStepStatus.COMPLETED
        except HTTPException as exc:
            # A missing prerequisite is the step's problem, not the run's: the
            # rest of the report is still worth having.
            step.status = AgentStepStatus.FAILED
            step.error_message = str(exc.detail)
        except Exception as exc:  # noqa: BLE001 - recorded on the step, run continues
            step.status = AgentStepStatus.FAILED
            step.error_message = f"{type(exc).__name__}: {exc}"

        step.completed_at = datetime.now(UTC)
        await db.flush()

    await db.refresh(run)
    run.summary_json = _summarize(run)
    run.status = AgentRunStatus.AWAITING_APPROVAL
    run.completed_at = datetime.now(UTC)
    # One commit for the whole run: a half-written report is worse than none,
    # and the steps are fast enough that holding the transaction is cheap.
    await db.commit()
    await db.refresh(run)
    return run


def _summarize(run: AgentRun) -> dict:
    by_key = {step.step_key: step for step in run.steps}
    limitation = by_key.get("limitation")
    gaps = by_key.get("gaps")
    upcoming = by_key.get("upcoming")
    return {
        "steps_total": len(run.steps),
        "steps_completed": sum(1 for s in run.steps if s.status is AgentStepStatus.COMPLETED),
        "steps_skipped": sum(1 for s in run.steps if s.status is AgentStepStatus.SKIPPED),
        "steps_failed": sum(1 for s in run.steps if s.status is AgentStepStatus.FAILED),
        "expired_deadlines": (limitation.output_json or {}).get("expired_count", 0)
        if limitation
        else 0,
        "unresolved_contradictions": (gaps.output_json or {}).get(
            "unresolved_contradiction_count", 0
        )
        if gaps
        else 0,
        "due_in_14_days": (upcoming.output_json or {}).get("item_count", 0) if upcoming else 0,
    }


async def get_run(db: AsyncSession, run_id: UUID) -> AgentRun:
    run = await db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


async def list_runs(db: AsyncSession, *, matter_id: UUID | None = None, limit: int = 50):
    stmt = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit)
    if matter_id is not None:
        stmt = stmt.where(AgentRun.matter_id == matter_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def review_run(
    db: AsyncSession,
    run_id: UUID,
    *,
    approved: bool,
    notes: str | None,
    reviewer: str | None,
) -> AgentRun:
    run = await get_run(db, run_id)
    if run.status is AgentRunStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Run has not finished")
    if run.status is AgentRunStatus.FAILED:
        raise HTTPException(status_code=409, detail="Run failed and cannot be approved")
    run.status = AgentRunStatus.APPROVED if approved else AgentRunStatus.REJECTED
    run.review_notes = notes
    run.reviewed_by = reviewer
    run.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(run)
    return run


def list_recipes() -> list[dict]:
    return [
        {
            "recipe": spec.recipe,
            "title": spec.title,
            "description": spec.description,
            "step_count": len(spec.steps),
            "deterministic_step_count": spec.deterministic_step_count,
        }
        for spec in RECIPES.values()
    ]
