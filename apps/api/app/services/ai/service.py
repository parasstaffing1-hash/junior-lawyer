from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.ai import (
    AICitationStatus,
    AIReviewStatus,
    AIRouteTier,
    AIRun,
    AIRunCitation,
    AIRunClaim,
    AIRunSource,
    AIRunStatus,
    AIUsageEvent,
    AIVerificationStatus,
)
from app.models.matter import Matter
from app.models.security import AuditOutcome, MatterAccessLevel
from app.services.security.context import get_current_actor
from app.services.security.permissions import decide_matter_access, remote_ai_allowed as security_remote_ai_allowed
from app.services.security.audit import append_audit_event
from app.schemas.ai import AIReasoningRequest, AIReviewRequest
from app.services.ai.prompting import estimate_tokens, system_prompt, user_prompt
from app.services.ai.providers import ProviderRegistry
from app.services.ai.retrieval import RetrievedSource, retrieve_sources
from app.services.ai.router import RouteDecision, route_task
from app.services.ai.verification import verify_response


def _run_options():
    return (
        selectinload(AIRun.sources),
        selectinload(AIRun.claims),
        selectinload(AIRun.citations),
        selectinload(AIRun.usage_events),
    )


async def provider_status() -> dict:
    return {
        "ai_enabled": settings.ai_enabled,
        "local_enabled": bool(settings.ai_enabled and settings.ai_local_enabled),
        "local_model": settings.ai_local_model if settings.ai_local_enabled else None,
        "remote_enabled": bool(settings.ai_enabled and settings.ai_remote_enabled and settings.ai_remote_api_key),
        "remote_model": settings.ai_remote_model if settings.ai_remote_enabled else None,
        "remote_calls_require_explicit_opt_in": True,
        "secrets_persisted": False,
    }


async def prepare_reasoning(db: AsyncSession, payload: AIReasoningRequest) -> dict:
    if payload.matter_id and not await db.get(Matter, payload.matter_id):
        raise HTTPException(status_code=404, detail="Matter not found")

    actor = get_current_actor()
    if actor is not None and payload.matter_id:
        matter_decision = await decide_matter_access(
            db, actor, payload.matter_id, required=MatterAccessLevel.WORK
        )
        if not matter_decision.allowed:
            raise HTTPException(status_code=403, detail=matter_decision.reason)
        if payload.allow_remote:
            remote_decision = await security_remote_ai_allowed(db, actor, payload.matter_id)
            if not remote_decision.allowed:
                raise HTTPException(status_code=403, detail=remote_decision.reason)
    elif actor is not None and payload.allow_remote:
        from app.services.security.service import get_policy
        policy = await get_policy(db, actor.organization_id)
        if not policy.allow_remote_ai_default:
            raise HTTPException(status_code=403, detail="Remote AI is disabled by organization policy")
        if policy.require_mfa_for_remote_ai and not actor.mfa_enrolled:
            raise HTTPException(status_code=403, detail="MFA is required for remote AI")

    decision = route_task(
        payload.task_type,
        settings=settings,
        prefer_local=payload.prefer_local,
        allow_remote=payload.allow_remote,
        allow_local_for_high_complexity=payload.allow_local_for_high_complexity,
    )

    if decision.tier == AIRouteTier.DETERMINISTIC:
        return {
            "routing": decision.as_dict(estimated_input_tokens=0, source_count=0),
            "sources": [],
            "prompt_preview": "No model prompt created. This task is routed to the deterministic service layer.",
            "budget": {"max_input_tokens": payload.max_input_tokens, "max_output_tokens": 0, "estimated_input_tokens": 0},
        }

    try:
        sources, retrieval_meta = await retrieve_sources(
            db,
            query=payload.query,
            matter_id=payload.matter_id,
            include_corpus=payload.include_corpus,
            max_sources=payload.max_sources,
            max_input_tokens=payload.max_input_tokens,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    system = system_prompt(payload.task_type, payload.output_language)
    user = user_prompt(task_type=payload.task_type, query=payload.query, sources=sources)
    estimated = estimate_tokens(system) + estimate_tokens(user)
    routing = decision.as_dict(estimated_input_tokens=estimated, source_count=len(sources))
    return {
        "routing": routing,
        "sources": sources,
        "prompt_preview": f"SYSTEM\n{system}\n\nUSER\n{user}",
        "budget": {
            "max_input_tokens": payload.max_input_tokens,
            "max_output_tokens": payload.max_output_tokens,
            "estimated_input_tokens": estimated,
            "within_budget": estimated <= payload.max_input_tokens,
            "retrieval": retrieval_meta,
        },
    }


async def run_reasoning(
    db: AsyncSession,
    payload: AIReasoningRequest,
    *,
    providers: ProviderRegistry | None = None,
) -> AIRun:
    prepared = await prepare_reasoning(db, payload)
    routing = prepared["routing"]
    tier = AIRouteTier(routing["tier"])
    sources: list[RetrievedSource] = prepared["sources"]
    estimated = int(prepared["budget"]["estimated_input_tokens"])

    row = AIRun(
        matter_id=payload.matter_id,
        task_type=payload.task_type,
        query=payload.query,
        output_language=payload.output_language,
        route_tier=tier,
        status=AIRunStatus.PREPARED,
        provider_key=routing.get("provider_key"),
        model_name=routing.get("model_name"),
        max_input_tokens=payload.max_input_tokens,
        max_output_tokens=payload.max_output_tokens,
        estimated_input_tokens=estimated,
        routing_json=routing,
        retrieval_json=prepared["budget"].get("retrieval") or {},
        request_snapshot_json={
            "matter_id": str(payload.matter_id) if payload.matter_id else None,
            "task_type": payload.task_type.value,
            "output_language": payload.output_language,
            "prefer_local": payload.prefer_local,
            "allow_remote": payload.allow_remote,
            "allow_local_for_high_complexity": payload.allow_local_for_high_complexity,
            "include_corpus": payload.include_corpus,
            "max_sources": payload.max_sources,
            "max_input_tokens": payload.max_input_tokens,
            "max_output_tokens": payload.max_output_tokens,
        },
    )
    db.add(row)
    await db.flush()
    actor = get_current_actor()
    if actor is not None and tier == AIRouteTier.STRONG:
        await append_audit_event(
            db,
            organization_id=actor.organization_id,
            actor=actor,
            action="ai.remote.request",
            resource_type="ai_run",
            resource_id=str(row.id),
            outcome=AuditOutcome.ALLOWED,
            metadata={
                "matter_id": str(payload.matter_id) if payload.matter_id else None,
                "task_type": payload.task_type.value,
                "source_count": len(sources),
                "model_name": row.model_name,
            },
        )
    for source in sources:
        db.add(AIRunSource(
            run_id=row.id,
            ordinal=source.ordinal,
            source_key=source.source_key,
            source_type=source.source_type,
            source_record_id=source.source_record_id,
            title=source.title,
            locator=source.locator,
            text=source.text,
            source_url=source.source_url,
            official=source.official,
            verified=source.verified,
            relevance_score=source.relevance_score,
            metadata_json=source.metadata_json,
        ))

    if tier == AIRouteTier.DETERMINISTIC:
        row.status = AIRunStatus.COMPLETED
        row.response_text = "This request was routed to the deterministic engine; no generative-model call was made."
        row.verification_status = AIVerificationStatus.PASSED
        row.verification_summary_json = {"provider_calls": 0, "deterministic": True}
        row.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return await get_run(db, row.id)

    if tier == AIRouteTier.BLOCKED:
        row.status = AIRunStatus.BLOCKED
        row.error_message = routing["reason"]
        await db.commit()
        return await get_run(db, row.id)

    if estimated > payload.max_input_tokens:
        row.status = AIRunStatus.BLOCKED
        row.error_message = "Prepared prompt exceeds the request input-token budget. Reduce source count or increase the explicit budget."
        await db.commit()
        return await get_run(db, row.id)

    registry = providers or ProviderRegistry.from_settings(settings)
    provider = registry.get(row.provider_key)
    if not provider:
        row.status = AIRunStatus.BLOCKED
        row.error_message = "The routed provider is not configured or available."
        await db.commit()
        return await get_run(db, row.id)

    row.status = AIRunStatus.RUNNING
    await db.commit()

    system = system_prompt(payload.task_type, payload.output_language)
    prompt = user_prompt(task_type=payload.task_type, query=payload.query, sources=sources)
    try:
        result = await provider.complete(system=system, user=prompt, max_output_tokens=payload.max_output_tokens)
    except Exception as exc:
        row.status = AIRunStatus.FAILED
        row.error_message = str(exc)[:4000]
        row.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return await get_run(db, row.id)

    row.response_text = result.content
    row.model_name = result.model_name
    row.actual_input_tokens = result.input_tokens
    row.actual_output_tokens = result.output_tokens
    db.add(AIUsageEvent(
        run_id=row.id,
        provider_key=row.provider_key or provider.key,
        model_name=result.model_name,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        latency_ms=result.latency_ms,
        provider_reported_cost_microunits=result.provider_reported_cost_microunits,
        currency=result.currency,
        metadata_json=result.metadata,
    ))

    verification = await verify_response(db, result.content, sources)
    for claim in verification.claims:
        db.add(AIRunClaim(
            run_id=row.id,
            ordinal=claim.ordinal,
            claim_text=claim.claim_text,
            substantive=claim.substantive,
            cited_source_keys_json=claim.cited_source_keys,
            support_score=claim.support_score,
            status=claim.status,
            explanation=claim.explanation,
        ))
    for citation in verification.citations:
        db.add(AIRunCitation(
            run_id=row.id,
            raw_citation=citation.raw_citation,
            normalized_citation=citation.normalized_citation,
            status=citation.status,
            matched_judgment_id=citation.matched_judgment_id,
            cited_source_keys_json=citation.cited_source_keys,
            metadata_json=citation.metadata,
        ))

    row.verification_status = {
        "passed": AIVerificationStatus.PASSED,
        "warnings": AIVerificationStatus.WARNINGS,
        "failed": AIVerificationStatus.FAILED,
    }[verification.status]
    row.verification_summary_json = verification.summary
    row.status = AIRunStatus.VERIFICATION_FAILED if verification.status == "failed" else AIRunStatus.COMPLETED
    row.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return await get_run(db, row.id)


async def get_run(db: AsyncSession, run_id: UUID) -> AIRun:
    row = await db.scalar(select(AIRun).where(AIRun.id == run_id).options(*_run_options()))
    if not row:
        raise HTTPException(status_code=404, detail="AI run not found")
    return row


async def list_runs(db: AsyncSession, *, matter_id: UUID | None = None, limit: int = 50) -> list[AIRun]:
    stmt = select(AIRun).options(*_run_options()).order_by(AIRun.created_at.desc()).limit(limit)
    if matter_id:
        stmt = stmt.where(AIRun.matter_id == matter_id)
    return list((await db.scalars(stmt)).unique().all())


async def review_run(db: AsyncSession, run_id: UUID, payload: AIReviewRequest) -> AIRun:
    row = await db.get(AIRun, run_id)
    if not row:
        raise HTTPException(status_code=404, detail="AI run not found")
    if payload.status == AIReviewStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review status must be reviewed or rejected")
    row.review_status = payload.status
    row.reviewed_by = payload.reviewed_by
    row.review_notes = payload.notes
    row.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return await get_run(db, row.id)
