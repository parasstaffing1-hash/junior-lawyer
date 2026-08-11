from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.security import OrganizationRole
from app.schemas.remedies import (
    RemedyAnalysisRead,
    RemedyAnalysisRequest,
    RemedyAuthorityRead,
    RemedyCandidateRead,
    RemedyCandidateReview,
    RemedyDraftCreate,
    RemedyDraftLinkRead,
    RemedyMemoCreate,
    RemedyMemoRead,
    RemedyRulePackCreate,
)
from app.services.remedies import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/remedies", tags=["legal-remedy-analysis"])
MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}


def _analysis_read(row, candidates_with_auths, warnings):
    candidates = []
    for candidate, auths in candidates_with_auths:
        candidates.append(RemedyCandidateRead(
            id=candidate.id,
            rule_id=candidate.rule_id,
            remedy_code=candidate.remedy_code,
            remedy_name_en=candidate.remedy_name_en,
            remedy_name_hi=candidate.remedy_name_hi,
            status=candidate.status,
            applicability_score=candidate.applicability_score,
            why_applicable_json=candidate.why_applicable_json,
            forum_json=candidate.forum_json,
            deadline_json=candidate.deadline_json,
            maintainability_json=candidate.maintainability_json,
            required_documents_json=candidate.required_documents_json,
            procedural_steps_json=candidate.procedural_steps_json,
            risks_json=candidate.risks_json,
            drafting_json=candidate.drafting_json,
            lawyer_note=candidate.lawyer_note,
            reviewed_by_membership_id=candidate.reviewed_by_membership_id,
            reviewed_at=candidate.reviewed_at,
            authorities=[RemedyAuthorityRead.model_validate(authority) for authority in auths],
        ))
    return RemedyAnalysisRead(
        id=row.id,
        organization_id=row.organization_id,
        matter_id=row.matter_id,
        saved_case_id=row.saved_case_id,
        language=row.language,
        status=row.status,
        case_snapshot_json=row.case_snapshot_json,
        context_json=row.context_json,
        disclaimer=row.disclaimer,
        analyzed_at=row.analyzed_at,
        candidates=candidates,
        coverage_warnings=warnings,
    )


@router.post("/rule-packs", status_code=201)
async def create_rule_pack(payload: RemedyRulePackCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    if actor.role not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Partner/admin/owner permission required to manage verified remedy packs")
    row = await service.create_rule_pack(db, actor, payload)
    return {"id": str(row.id), "code": row.code, "version": row.version, "status": row.status, "verified": row.verified}


@router.get("/rule-packs")
async def rule_packs(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    rows = await service.list_rule_packs(db)
    return [{"id": str(row.id), "code": row.code, "name_en": row.name_en, "name_hi": row.name_hi, "jurisdiction": row.jurisdiction, "version": row.version, "status": row.status, "verified": row.verified} for row in rows]


@router.post("/analyze", response_model=RemedyAnalysisRead, status_code=201)
async def analyze(payload: RemedyAnalysisRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row, _candidates, warnings = await service.analyze(db, actor, payload)
    row, enriched, warnings = await service.get_analysis(db, actor, row.id)
    return _analysis_read(row, enriched, warnings)


@router.get("/analyses/{analysis_id}", response_model=RemedyAnalysisRead)
async def analysis_detail(analysis_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row, enriched, warnings = await service.get_analysis(db, actor, analysis_id)
    return _analysis_read(row, enriched, warnings)


@router.get("/matters/{matter_id}", response_model=list[RemedyAnalysisRead])
async def matter_analyses(matter_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    rows = await service.list_analyses(db, actor, matter_id=matter_id)
    output = []
    for row in rows:
        detail, enriched, warnings = await service.get_analysis(db, actor, row.id)
        output.append(_analysis_read(detail, enriched, warnings))
    return output


@router.patch("/candidates/{candidate_id}", response_model=RemedyCandidateRead)
async def review_candidate(candidate_id: UUID, payload: RemedyCandidateReview, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row = await service.review_candidate(db, actor, candidate_id, candidate_status=payload.status, note=payload.lawyer_note)
    analysis, enriched, _ = await service.get_analysis(db, actor, row.analysis_id)
    candidate, auths = next((item for item in enriched if item[0].id == row.id))
    return RemedyCandidateRead(
        id=candidate.id, rule_id=candidate.rule_id, remedy_code=candidate.remedy_code, remedy_name_en=candidate.remedy_name_en,
        remedy_name_hi=candidate.remedy_name_hi, status=candidate.status, applicability_score=candidate.applicability_score,
        why_applicable_json=candidate.why_applicable_json, forum_json=candidate.forum_json, deadline_json=candidate.deadline_json,
        maintainability_json=candidate.maintainability_json, required_documents_json=candidate.required_documents_json,
        procedural_steps_json=candidate.procedural_steps_json, risks_json=candidate.risks_json, drafting_json=candidate.drafting_json,
        lawyer_note=candidate.lawyer_note, reviewed_by_membership_id=candidate.reviewed_by_membership_id, reviewed_at=candidate.reviewed_at,
        authorities=[RemedyAuthorityRead.model_validate(a) for a in auths],
    )


@router.post("/candidates/{candidate_id}/memo", response_model=RemedyMemoRead, status_code=201)
async def memo(candidate_id: UUID, payload: RemedyMemoCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return RemedyMemoRead.model_validate(await service.create_memo(db, actor, candidate_id, payload.language))


@router.post("/candidates/{candidate_id}/draft", response_model=RemedyDraftLinkRead, status_code=201)
async def draft(candidate_id: UUID, payload: RemedyDraftCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return RemedyDraftLinkRead.model_validate(await service.create_remedy_draft(db, actor, candidate_id, payload))
