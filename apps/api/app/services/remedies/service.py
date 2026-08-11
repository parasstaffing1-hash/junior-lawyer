from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_lookup import SavedCase, SavedCaseOrder, SavedCaseJudgment
from app.models.document import Document
from app.models.drafting import DraftSourceType, LegalDraftLanguage, LegalDraftType
from app.models.matter import Matter
from app.models.operations import CourtCaseSnapshot, CourtCaseTracker
from app.models.procedure import Hearing
from app.models.remedies import (
    RemedyAnalysis,
    RemedyAnalysisStatus,
    RemedyCandidate,
    RemedyCandidateAuthority,
    RemedyCandidateStatus,
    RemedyDraftLink,
    RemedyMemo,
    RemedyMemoStatus,
    RemedyPackStatus,
    RemedyRule,
    RemedyRuleAuthority,
    RemedyRulePack,
)
from app.schemas.drafting import AuthorityReference, LegalDraftCreate
from app.schemas.remedies import RemedyAnalysisRequest, RemedyDraftCreate, RemedyRulePackCreate
from app.services.case_lookup.service import record_from_saved
from app.services.drafting.service import create_draft
from app.services.remedies.engine import evaluate_rule, research_hints
from app.services.security.context import ActorContext
from app.services.security.permissions import MatterAccessLevel, enforce_current_matter_access


DISCLAIMER = (
    "Legal Remedy Analysis is a lawyer decision-support tool. A listed remedy is not a legal opinion or guarantee of maintainability. "
    "Verify the controlling statute/rule, forum, appealability/revisionability, limitation computation, exclusions, condonation, alternate-remedy doctrine, "
    "territorial/pecuniary jurisdiction and the latest binding precedent before filing."
)


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


async def create_rule_pack(db: AsyncSession, actor: ActorContext, payload: RemedyRulePackCreate) -> RemedyRulePack:
    if payload.status == RemedyPackStatus.ACTIVE or payload.verified:
        if not payload.verified:
            raise HTTPException(status_code=400, detail="Active remedy packs must be verified")
        for rule in payload.rules:
            if not rule.verified:
                raise HTTPException(status_code=400, detail=f"Verified/active pack contains unverified rule: {rule.code}")
            if not any(authority.verified for authority in rule.authorities):
                raise HTTPException(status_code=400, detail=f"Rule {rule.code} requires at least one verified authority before activation")
    pack = RemedyRulePack(
        code=payload.code,
        name_en=payload.name_en,
        name_hi=payload.name_hi,
        jurisdiction=payload.jurisdiction,
        proceeding_type=payload.proceeding_type,
        court_level=payload.court_level,
        version=payload.version,
        status=payload.status,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        source_name=payload.source_name,
        source_url=payload.source_url,
        source_citation=payload.source_citation,
        verified=payload.verified,
        metadata_json={**payload.metadata_json, "created_by_membership_id": str(actor.membership_id)},
    )
    db.add(pack)
    await db.flush()
    for item in payload.rules:
        rule = RemedyRule(
            pack_id=pack.id,
            code=item.code,
            remedy_name_en=item.remedy_name_en,
            remedy_name_hi=item.remedy_name_hi,
            description_en=item.description_en,
            description_hi=item.description_hi,
            priority=item.priority,
            case_stage_patterns_json=item.case_stage_patterns_json,
            status_patterns_json=item.status_patterns_json,
            court_level_patterns_json=item.court_level_patterns_json,
            order_type_patterns_json=item.order_type_patterns_json,
            act_patterns_json=item.act_patterns_json,
            section_patterns_json=item.section_patterns_json,
            requires_final_order=item.requires_final_order,
            requires_latest_order=item.requires_latest_order,
            forum_json=item.forum_json,
            limitation_json=item.limitation_json,
            maintainability_json=item.maintainability_json,
            required_documents_json=item.required_documents_json,
            procedural_steps_json=item.procedural_steps_json,
            risks_json=item.risks_json,
            drafting_json=item.drafting_json,
            verified=item.verified,
            metadata_json=item.metadata_json,
        )
        db.add(rule)
        await db.flush()
        for authority in item.authorities:
            db.add(RemedyRuleAuthority(
                rule_id=rule.id,
                authority_type=authority.authority_type,
                statute_section_id=authority.statute_section_id,
                judgment_id=authority.judgment_id,
                citation=authority.citation,
                proposition=authority.proposition,
                source_url=authority.source_url,
                verified=authority.verified,
            ))
    await db.commit()
    await db.refresh(pack)
    return pack


async def list_rule_packs(db: AsyncSession) -> list[RemedyRulePack]:
    return list((await db.scalars(select(RemedyRulePack).order_by(RemedyRulePack.code, RemedyRulePack.version.desc()))).all())


async def _case_context(db: AsyncSession, actor: ActorContext, payload: RemedyAnalysisRequest) -> tuple[dict, UUID | None, UUID | None]:
    saved_case: SavedCase | None = None
    matter: Matter | None = None
    if payload.saved_case_id:
        saved_case = await db.get(SavedCase, payload.saved_case_id)
        if not saved_case or saved_case.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Saved case not found")
        if saved_case.matter_id:
            await enforce_current_matter_access(db, saved_case.matter_id, required=MatterAccessLevel.VIEW)
            matter = await db.get(Matter, saved_case.matter_id)
    if payload.matter_id:
        await enforce_current_matter_access(db, payload.matter_id, required=MatterAccessLevel.VIEW)
        matter = await db.get(Matter, payload.matter_id)
        if not matter:
            raise HTTPException(status_code=404, detail="Matter not found")
        if saved_case is None:
            saved_case = await db.scalar(select(SavedCase).where(SavedCase.organization_id == actor.organization_id, SavedCase.matter_id == matter.id).order_by(SavedCase.updated_at.desc()))
    if not matter and not saved_case:
        raise HTTPException(status_code=400, detail="Provide matter_id or saved_case_id")

    if saved_case:
        context = await record_from_saved(db, saved_case)
        matter_id = saved_case.matter_id or (matter.id if matter else None)
        saved_case_id = saved_case.id
    else:
        assert matter is not None
        tracker = await db.scalar(select(CourtCaseTracker).where(CourtCaseTracker.matter_id == matter.id).order_by(CourtCaseTracker.updated_at.desc()))
        snapshot = None
        if tracker:
            snapshot = await db.scalar(select(CourtCaseSnapshot).where(CourtCaseSnapshot.tracker_id == tracker.id).order_by(CourtCaseSnapshot.captured_at.desc()))
        hearings = list((await db.scalars(select(Hearing).where(Hearing.matter_id == matter.id).order_by(Hearing.scheduled_for))).all())
        context = {
            "cnr": matter.cnr_number,
            "case_number": matter.case_number or matter.reference_number or str(matter.id),
            "case_type": None,
            "year": None,
            "case_title": matter.title,
            "court_name": matter.court_name or (tracker.court_name if tracker else None),
            "court_level": None,
            "state": matter.jurisdiction,
            "status": snapshot.case_status if snapshot else _enum_value(matter.status),
            "case_stage": snapshot.stage if snapshot else None,
            "judge": snapshot.judge_or_bench if snapshot else None,
            "bench": tracker.bench_name if tracker else None,
            "previous_hearing_date": None,
            "next_hearing_date": snapshot.next_hearing_date if snapshot else None,
            "parties": [], "advocates": [], "acts": [], "orders": [], "judgments": [],
            "hearing_history": [{"hearing_date": h.scheduled_for.date().isoformat(), "purpose_or_stage": h.purpose, "judge_or_bench": h.judge_or_bench} for h in hearings],
            "source_name": "Junior Lawyer matter + court tracker",
            "source_kind": "saved",
            "fetched_at": datetime.now(UTC).isoformat(),
        }
        matter_id = matter.id
        saved_case_id = None

    context["matter_id"] = str(matter_id) if matter_id else None
    context["saved_case_id"] = str(saved_case_id) if saved_case_id else None
    if matter_id:
        docs = list((await db.scalars(select(Document).where(Document.matter_id == matter_id))).all())
        context["document_titles"] = [doc.filename for doc in docs]
    else:
        context["document_titles"] = []
    return context, matter_id, saved_case_id


def _document_requirements(specs: list, context: dict) -> list:
    titles = " ".join(context.get("document_titles", [])).casefold()
    has_order = bool(context.get("orders") or context.get("judgments"))
    output = []
    for item in specs:
        spec = {"name": item} if isinstance(item, str) else dict(item)
        name = str(spec.get("name") or spec.get("label") or "Required document")
        keys = spec.get("match_terms") or [name]
        available = any(str(term).casefold() in titles for term in keys if str(term).strip())
        if spec.get("source") == "latest_order":
            available = has_order
        output.append({**spec, "name": name, "available": bool(available)})
    return output


async def analyze(db: AsyncSession, actor: ActorContext, payload: RemedyAnalysisRequest) -> tuple[RemedyAnalysis, list[RemedyCandidate], list[str]]:
    context, matter_id, saved_case_id = await _case_context(db, actor, payload)
    as_of = payload.as_of_date or date.today()
    jurisdiction = str(context.get("state") or "India")
    court_level = str(context.get("court_level") or "")

    pack_stmt = select(RemedyRulePack).where(
        RemedyRulePack.status == RemedyPackStatus.ACTIVE,
        RemedyRulePack.verified.is_(True),
        or_(RemedyRulePack.effective_from.is_(None), RemedyRulePack.effective_from <= as_of),
        or_(RemedyRulePack.effective_to.is_(None), RemedyRulePack.effective_to >= as_of),
    )
    packs = list((await db.scalars(pack_stmt)).all())
    pack_ids = [pack.id for pack in packs if pack.jurisdiction.casefold() in {"india", jurisdiction.casefold()} and (not pack.court_level or pack.court_level.casefold() in court_level.casefold())]
    rules = list((await db.scalars(select(RemedyRule).where(RemedyRule.pack_id.in_(pack_ids), RemedyRule.verified.is_(True)).order_by(RemedyRule.priority.desc()))).all()) if pack_ids else []

    analysis = RemedyAnalysis(
        organization_id=actor.organization_id,
        matter_id=matter_id,
        saved_case_id=saved_case_id,
        created_by_membership_id=actor.membership_id,
        language=payload.language,
        status=RemedyAnalysisStatus.REVIEW_REQUIRED,
        case_snapshot_json=context,
        context_json={"as_of_date": as_of.isoformat(), "pack_count": len(pack_ids), "rule_count": len(rules)},
        disclaimer=DISCLAIMER,
        analyzed_at=datetime.now(UTC),
    )
    db.add(analysis)
    await db.flush()

    candidates: list[RemedyCandidate] = []
    for rule in rules:
        result = evaluate_rule(rule, context, as_of_date=as_of, language=payload.language)
        if not result:
            continue
        candidate = RemedyCandidate(
            analysis_id=analysis.id,
            rule_id=rule.id,
            remedy_code=rule.code,
            remedy_name_en=rule.remedy_name_en,
            remedy_name_hi=rule.remedy_name_hi,
            status=RemedyCandidateStatus(result["status"]),
            applicability_score=result["score"],
            why_applicable_json=result["reasons"],
            forum_json={**rule.forum_json, "current_court": context.get("court_name"), "current_court_level": context.get("court_level")},
            deadline_json=result["deadline"],
            maintainability_json=result["maintainability"],
            required_documents_json=_document_requirements(rule.required_documents_json, context),
            procedural_steps_json=rule.procedural_steps_json,
            risks_json=rule.risks_json,
            drafting_json=rule.drafting_json,
        )
        db.add(candidate)
        await db.flush()
        auths = list((await db.scalars(select(RemedyRuleAuthority).where(RemedyRuleAuthority.rule_id == rule.id, RemedyRuleAuthority.verified.is_(True)))).all())
        for authority in auths:
            db.add(RemedyCandidateAuthority(
                candidate_id=candidate.id,
                authority_type=authority.authority_type,
                statute_section_id=authority.statute_section_id,
                judgment_id=authority.judgment_id,
                citation=authority.citation,
                proposition=authority.proposition,
                source_url=authority.source_url,
                verified=True,
                source_rank=100,
            ))
        candidates.append(candidate)

    warnings: list[str] = []
    if not pack_ids:
        warnings.append("No active verified remedy rule pack covers this case context. No unsupported remedy is being asserted.")
    if not candidates:
        hints = research_hints(context)
        analysis.context_json = {**analysis.context_json, "research_hints": hints}
        if hints:
            warnings.append("Procedural posture produced research prompts only. They are not maintainability conclusions until a verified rule/authority is attached.")
    if any(not item.deadline_json.get("calculated") for item in candidates):
        warnings.append("At least one remedy deadline could not be calculated from verified rule data and case trigger dates; lawyer review is required.")
    analysis.context_json = {**analysis.context_json, "coverage_warnings": warnings}
    await db.commit()
    return analysis, candidates, warnings


async def list_analyses(db: AsyncSession, actor: ActorContext, matter_id: UUID | None = None, saved_case_id: UUID | None = None) -> list[RemedyAnalysis]:
    stmt = select(RemedyAnalysis).where(RemedyAnalysis.organization_id == actor.organization_id)
    if matter_id:
        await enforce_current_matter_access(db, matter_id, required=MatterAccessLevel.VIEW)
        stmt = stmt.where(RemedyAnalysis.matter_id == matter_id)
    if saved_case_id:
        stmt = stmt.where(RemedyAnalysis.saved_case_id == saved_case_id)
    return list((await db.scalars(stmt.order_by(RemedyAnalysis.analyzed_at.desc()).limit(100))).all())


async def get_analysis(db: AsyncSession, actor: ActorContext, analysis_id: UUID) -> tuple[RemedyAnalysis, list[tuple[RemedyCandidate, list[RemedyCandidateAuthority]]], list[str]]:
    row = await db.get(RemedyAnalysis, analysis_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Remedy analysis not found")
    if row.matter_id:
        await enforce_current_matter_access(db, row.matter_id, required=MatterAccessLevel.VIEW)
    candidates = list((await db.scalars(select(RemedyCandidate).where(RemedyCandidate.analysis_id == row.id).order_by(RemedyCandidate.applicability_score.desc()))).all())
    enriched = []
    for candidate in candidates:
        auths = list((await db.scalars(select(RemedyCandidateAuthority).where(RemedyCandidateAuthority.candidate_id == candidate.id).order_by(RemedyCandidateAuthority.source_rank.desc()))).all())
        enriched.append((candidate, auths))
    return row, enriched, list(row.context_json.get("coverage_warnings") or [])


async def review_candidate(db: AsyncSession, actor: ActorContext, candidate_id: UUID, *, candidate_status: RemedyCandidateStatus | None, note: str | None) -> RemedyCandidate:
    row = await db.get(RemedyCandidate, candidate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Remedy candidate not found")
    analysis = await db.get(RemedyAnalysis, row.analysis_id)
    if not analysis or analysis.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Remedy candidate not found")
    if analysis.matter_id:
        await enforce_current_matter_access(db, analysis.matter_id, required=MatterAccessLevel.WORK)
    if candidate_status is not None:
        row.status = candidate_status
    if note is not None:
        row.lawyer_note = note
    row.reviewed_by_membership_id = actor.membership_id
    row.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return row


def _memo_text(candidate: RemedyCandidate, authorities: list[RemedyCandidateAuthority], language: str) -> str:
    english = [
        f"LEGAL REMEDY MEMO — {candidate.remedy_name_en}",
        "",
        "Status: Lawyer review required.",
        "",
        "WHY THIS REMEDY MAY APPLY",
        *[f"- {item}" for item in candidate.why_applicable_json],
        "",
        "FORUM",
        f"- {candidate.forum_json}",
        "",
        "LIMITATION / DEADLINE",
        f"- {candidate.deadline_json}",
        "",
        "MAINTAINABILITY",
        *[f"- {check.get('label')}: {'met' if check.get('passed') is True else 'not met' if check.get('passed') is False else 'needs review'}" for check in candidate.maintainability_json.get('checks', [])],
        "",
        "REQUIRED DOCUMENTS / EVIDENCE",
        *[f"- {item.get('name', item)} — {'available' if isinstance(item, dict) and item.get('available') else 'verify/obtain'}" for item in candidate.required_documents_json],
        "",
        "PROCEDURAL NEXT STEPS",
        *[f"{idx}. {step}" for idx, step in enumerate(candidate.procedural_steps_json, start=1)],
        "",
        "RISKS / CONDITIONS",
        *[f"- {item}" for item in candidate.risks_json],
        "",
        "VERIFIED AUTHORITIES",
        *[f"- {a.citation or a.authority_type}: {a.proposition}" for a in authorities if a.verified],
        "",
        DISCLAIMER,
    ]
    hindi = [
        f"कानूनी उपचार ज्ञापन — {candidate.remedy_name_hi or candidate.remedy_name_en}",
        "",
        "स्थिति: वकील द्वारा समीक्षा आवश्यक।",
        "",
        "यह उपचार क्यों लागू हो सकता है",
        *[f"- {item}" for item in candidate.why_applicable_json],
        "",
        "उचित मंच / न्यायालय",
        f"- {candidate.forum_json}",
        "",
        "सीमा अवधि / महत्वपूर्ण समय-सीमा",
        f"- {candidate.deadline_json}",
        "",
        "पोषणीयता / Maintainability",
        *[f"- {check.get('label')}: {'पूर्ण' if check.get('passed') is True else 'पूर्ण नहीं' if check.get('passed') is False else 'समीक्षा आवश्यक'}" for check in candidate.maintainability_json.get('checks', [])],
        "",
        "आवश्यक दस्तावेज / साक्ष्य",
        *[f"- {item.get('name', item)} — {'उपलब्ध' if isinstance(item, dict) and item.get('available') else 'सत्यापित/प्राप्त करें'}" for item in candidate.required_documents_json],
        "",
        "अगले प्रक्रियात्मक कदम",
        *[f"{idx}. {step}" for idx, step in enumerate(candidate.procedural_steps_json, start=1)],
        "",
        "जोखिम / शर्तें",
        *[f"- {item}" for item in candidate.risks_json],
        "",
        "सत्यापित प्राधिकार",
        *[f"- {a.citation or a.authority_type}: {a.proposition}" for a in authorities if a.verified],
        "",
        "यह वकील सहायता उपकरण है; दाखिल करने से पहले लागू कानून, मंच, सीमा और नवीन बाध्यकारी निर्णय सत्यापित करें।",
    ]
    if language == "hi":
        return "\n".join(hindi)
    if language == "bilingual":
        return "\n".join(english) + "\n\n--- हिन्दी ---\n\n" + "\n".join(hindi)
    return "\n".join(english)


async def create_memo(db: AsyncSession, actor: ActorContext, candidate_id: UUID, language: str) -> RemedyMemo:
    row = await db.get(RemedyCandidate, candidate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Remedy candidate not found")
    analysis = await db.get(RemedyAnalysis, row.analysis_id)
    if not analysis or analysis.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Remedy candidate not found")
    if analysis.matter_id:
        await enforce_current_matter_access(db, analysis.matter_id, required=MatterAccessLevel.WORK)
    auths = list((await db.scalars(select(RemedyCandidateAuthority).where(RemedyCandidateAuthority.candidate_id == row.id))).all())
    memo = RemedyMemo(
        candidate_id=row.id,
        language=language,
        status=RemedyMemoStatus.REVIEW_REQUIRED,
        content=_memo_text(row, auths, language),
        source_snapshot_json={
            "analysis_id": str(analysis.id),
            "case_snapshot": analysis.case_snapshot_json,
            "authority_ids": [str(a.id) for a in auths if a.verified],
        },
        generated_deterministically=True,
    )
    db.add(memo)
    await db.commit()
    await db.refresh(memo)
    return memo


DRAFT_KIND_MAP = {
    "appeal": LegalDraftType.PETITION,
    "revision": LegalDraftType.PETITION,
    "review": LegalDraftType.PETITION,
    "writ": LegalDraftType.PETITION,
    "quashing": LegalDraftType.PETITION,
    "bail": LegalDraftType.APPLICATION,
    "stay": LegalDraftType.APPLICATION,
    "injunction": LegalDraftType.APPLICATION,
    "execution": LegalDraftType.APPLICATION,
    "restoration": LegalDraftType.APPLICATION,
    "recall": LegalDraftType.APPLICATION,
    "application": LegalDraftType.APPLICATION,
    "petition": LegalDraftType.PETITION,
}


async def create_remedy_draft(db: AsyncSession, actor: ActorContext, candidate_id: UUID, payload: RemedyDraftCreate):
    candidate = await db.get(RemedyCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Remedy candidate not found")
    analysis = await db.get(RemedyAnalysis, candidate.analysis_id)
    if not analysis or analysis.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Remedy candidate not found")
    if not analysis.matter_id:
        raise HTTPException(status_code=409, detail="Link/save the case to a Matter workspace before generating a legal draft")
    await enforce_current_matter_access(db, analysis.matter_id, required=MatterAccessLevel.WORK)
    kind = payload.requested_document_kind.casefold().strip()
    draft_type = DRAFT_KIND_MAP.get(kind) or DRAFT_KIND_MAP.get(str(candidate.drafting_json.get("draft_type") or "").casefold()) or LegalDraftType.APPLICATION
    language = LegalDraftLanguage.BILINGUAL if payload.language == "bilingual" else LegalDraftLanguage.HINDI if payload.language == "hi" else LegalDraftLanguage.ENGLISH
    authorities = list((await db.scalars(select(RemedyCandidateAuthority).where(RemedyCandidateAuthority.candidate_id == candidate.id, RemedyCandidateAuthority.verified.is_(True)))).all())
    authority_refs = []
    for authority in authorities:
        if authority.statute_section_id:
            authority_refs.append(AuthorityReference(source_type=DraftSourceType.STATUTE_SECTION, source_id=authority.statute_section_id))
    provision = candidate.drafting_json.get("heading") or candidate.remedy_name_en
    relief = payload.relief_requested or candidate.drafting_json.get("default_relief") or f"Relief appropriate to the selected remedy: {candidate.remedy_name_en}. Counsel must confirm the exact prayer."
    draft = await create_draft(db, LegalDraftCreate(
        matter_id=analysis.matter_id,
        draft_type=draft_type,
        language=language,
        title=f"{candidate.remedy_name_en} — remedy draft",
        questionnaire_json={
            "application_heading": provision,
            "petition_heading": provision,
            "grounds": payload.additional_instructions or "[Grounds must be finalized by counsel from the verified remedy analysis and record.]",
            "relief_requested": relief,
        },
        authority_refs=authority_refs,
    ))
    link = RemedyDraftLink(
        candidate_id=candidate.id,
        legal_draft_id=draft.id,
        requested_document_kind=payload.requested_document_kind,
        created_by_membership_id=actor.membership_id,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link
