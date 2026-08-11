from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.drafting import (
    DraftFindingLevel,
    DraftFindingStatus,
    DraftSectionSource,
    DraftSourceType,
    LegalDraft,
    LegalDraftFinding,
    LegalDraftSection,
    LegalDraftSource,
    LegalDraftStatus,
    LegalDraftTemplate,
    LegalDraftType,
    LegalDraftVersion,
)
from app.models.intelligence import (
    MatterContradiction,
    MatterFact,
    MatterStatement,
    TimelineEvent,
)
from app.models.legal_corpus import Judgment, JudgmentParagraph, Statute, StatuteSection
from app.models.matter import Matter
from app.models.security import MatterAccessLevel
from app.services.security.context import get_current_actor
from app.services.security.permissions import decide_matter_access, visible_matter_ids
from app.schemas.drafting import LegalDraftCreate, LegalDraftUpdate
from app.services.drafting.builder import build_sections, health_score, safe_facts
from app.services.drafting.catalog import DRAFT_DEFINITIONS
from app.services.drafting.renderer import generate_docx, resolve_draft_storage_key


def _draft_options():
    return (
        selectinload(LegalDraft.sections).selectinload(LegalDraftSection.sources),
        selectinload(LegalDraft.findings),
        selectinload(LegalDraft.versions),
    )


async def seed_templates(db: AsyncSession) -> int:
    created = 0
    for code, definition in DRAFT_DEFINITIONS.items():
        existing = await db.scalar(
            select(LegalDraftTemplate).where(
                LegalDraftTemplate.code == code,
                LegalDraftTemplate.version == 1,
            )
        )
        if existing:
            continue
        db.add(LegalDraftTemplate(
            code=code,
            draft_type=LegalDraftType(code),
            name_en=definition["name_en"],
            name_hi=definition["name_hi"],
            description=definition["description"],
            structure_json=definition["sections"],
            questions_json=definition["questions"],
            version=1,
            active=True,
            metadata_json={"source": "builtin", "generator": "deterministic_builder_v1"},
        ))
        created += 1
    await db.commit()
    return created


async def list_templates(db: AsyncSession) -> list[LegalDraftTemplate]:
    return list((await db.scalars(
        select(LegalDraftTemplate)
        .where(LegalDraftTemplate.active.is_(True))
        .order_by(LegalDraftTemplate.name_en)
    )).all())


async def get_draft(db: AsyncSession, draft_id: UUID) -> LegalDraft:
    draft = await db.scalar(
        select(LegalDraft).where(LegalDraft.id == draft_id).options(*_draft_options())
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal draft not found")
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_matter_access(db, actor, draft.matter_id, required=MatterAccessLevel.VIEW)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    return draft


def _document_locator(document: Document | None, page_number: int | None) -> str | None:
    if not document:
        return f"Page {page_number}" if page_number else None
    label = document.display_name or document.filename
    return f"{label} · p.{page_number}" if page_number else label


async def _matter_context(
    db: AsyncSession,
    matter_id: UUID,
    *,
    selected_fact_ids: list[UUID] | None = None,
    selected_event_ids: list[UUID] | None = None,
) -> dict:
    matter = await db.get(Matter, matter_id)
    if not matter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_matter_access(db, actor, matter_id, required=MatterAccessLevel.VIEW)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)

    documents = list((await db.scalars(
        select(Document).where(Document.matter_id == matter_id).order_by(Document.created_at)
    )).all())
    document_map = {item.id: item for item in documents}

    fact_stmt = (
        select(MatterFact)
        .where(MatterFact.matter_id == matter_id)
        .options(selectinload(MatterFact.sources))
        .order_by(MatterFact.category, MatterFact.label)
    )
    if selected_fact_ids:
        fact_stmt = fact_stmt.where(MatterFact.id.in_(selected_fact_ids))
    facts = list((await db.scalars(fact_stmt)).unique().all())

    event_stmt = (
        select(TimelineEvent)
        .where(TimelineEvent.matter_id == matter_id)
        .options(selectinload(TimelineEvent.sources))
        .order_by(TimelineEvent.event_date, TimelineEvent.created_at)
    )
    if selected_event_ids:
        event_stmt = event_stmt.where(TimelineEvent.id.in_(selected_event_ids))
    events = list((await db.scalars(event_stmt)).unique().all())

    statements = list((await db.scalars(
        select(MatterStatement)
        .where(MatterStatement.matter_id == matter_id)
        .order_by(MatterStatement.created_at)
    )).all())
    contradictions = list((await db.scalars(
        select(MatterContradiction)
        .where(MatterContradiction.matter_id == matter_id)
        .order_by(MatterContradiction.severity.desc(), MatterContradiction.created_at)
    )).all())

    fact_dicts: list[dict] = []
    for fact in facts:
        primary = fact.sources[0] if fact.sources else None
        source_doc = document_map.get(primary.document_id) if primary else None
        fact_dicts.append({
            "id": fact.id,
            "label": fact.label,
            "value": fact.value_text,
            "status": fact.status.value,
            "confidence": fact.confidence,
            "source": {
                "locator": _document_locator(source_doc, primary.page_number),
                "excerpt": primary.quote,
            } if primary else {},
            "all_sources": [str(source.id) for source in fact.sources],
        })

    contradiction_dicts = [{
        "id": item.id,
        "label": item.label,
        "severity": item.severity.value,
        "status": item.status.value,
        "values": [value.get("display") or value.get("value") for value in item.values_json],
        "fact_ids": item.fact_ids_json,
    } for item in contradictions]
    safe, excluded = safe_facts(fact_dicts, contradiction_dicts)

    event_dicts: list[dict] = []
    for event in events:
        primary = event.sources[0] if event.sources else None
        source_doc = document_map.get(primary.document_id) if primary else None
        event_dicts.append({
            "id": event.id,
            "date": event.event_date,
            "title": event.title,
            "description": event.description,
            "confidence": event.confidence,
            "source": {
                "locator": _document_locator(source_doc, primary.page_number),
                "excerpt": primary.quote,
            } if primary else {},
        })

    statement_dicts = []
    for statement in statements:
        document = document_map.get(statement.document_id)
        statement_dicts.append({
            "id": statement.id,
            "kind": statement.kind.value,
            "text": statement.raw_text,
            "speaker_role": statement.speaker_role,
            "locator": _document_locator(document, statement.page_number),
        })

    return {
        "matter": matter,
        "matter_title": matter.title,
        "client_name": matter.client_name,
        "court_name": matter.court_name,
        "case_number": matter.case_number,
        "facts": fact_dicts,
        "safe_facts": safe,
        "excluded_facts": excluded,
        "timeline": event_dicts,
        "documents": [{
            "id": item.id,
            "name": item.display_name or item.filename,
            "pages": item.page_count,
            "language": item.detected_language.value,
        } for item in documents],
        "statements": statement_dicts,
        "contradictions": contradiction_dicts,
    }


async def context_preview(db: AsyncSession, matter_id: UUID) -> dict:
    context = await _matter_context(db, matter_id)
    return {
        "matter_id": matter_id,
        "matter_title": context["matter_title"],
        "court_name": context["court_name"],
        "case_number": context["case_number"],
        "available_facts": len(context["facts"]),
        "safe_facts": len(context["safe_facts"]),
        "excluded_conflicting_facts": len(context["excluded_facts"]),
        "timeline_events": len(context["timeline"]),
        "documents": len(context["documents"]),
        "admissions": sum(1 for item in context["statements"] if item["kind"] == "admission"),
        "denials": sum(1 for item in context["statements"] if item["kind"] == "denial"),
        "open_contradictions": sum(1 for item in context["contradictions"] if item["status"] == "open"),
    }


async def _resolve_authorities(db: AsyncSession, refs: list) -> list[dict]:
    authorities: list[dict] = []
    for ref in refs:
        source_type = ref.source_type.value if hasattr(ref.source_type, "value") else str(ref.source_type)
        if source_type == DraftSourceType.STATUTE_SECTION.value:
            row = await db.execute(
                select(StatuteSection, Statute)
                .join(Statute, StatuteSection.statute_id == Statute.id)
                .where(StatuteSection.id == ref.source_id)
            )
            result = row.first()
            if not result:
                authorities.append({
                    "source_type": source_type,
                    "source_id": ref.source_id,
                    "label": "Unresolved statute section",
                    "locator": None,
                    "excerpt": None,
                    "verified": False,
                })
                continue
            section, statute = result
            excerpt = section.text_en or section.text_hi or section.normalized_text
            authorities.append({
                "source_type": source_type,
                "source_id": section.id,
                "label": f"{statute.title_en} — {section.provision_type.title()} {section.section_number}",
                "locator": section.source_url or statute.source_url,
                "excerpt": (excerpt or "")[:800],
                "verified": True,
                "metadata": {"statute_id": str(statute.id)},
            })
        elif source_type == DraftSourceType.JUDGMENT_PARAGRAPH.value:
            row = await db.execute(
                select(JudgmentParagraph, Judgment)
                .join(Judgment, JudgmentParagraph.judgment_id == Judgment.id)
                .where(JudgmentParagraph.id == ref.source_id)
            )
            result = row.first()
            if not result:
                authorities.append({
                    "source_type": source_type,
                    "source_id": ref.source_id,
                    "label": "Unresolved judgment paragraph",
                    "locator": None,
                    "excerpt": None,
                    "verified": False,
                })
                continue
            paragraph, judgment = result
            citation = judgment.neutral_citation or (judgment.reported_citations_json[0] if judgment.reported_citations_json else judgment.case_number)
            para = paragraph.paragraph_number or str(paragraph.position)
            authorities.append({
                "source_type": source_type,
                "source_id": paragraph.id,
                "label": f"{judgment.case_title}{' — ' + citation if citation else ''}",
                "locator": f"¶ {para}",
                "excerpt": paragraph.text[:1000],
                "verified": True,
                "metadata": {"judgment_id": str(judgment.id), "source_url": judgment.source_url},
            })
        else:
            authorities.append({
                "source_type": source_type,
                "source_id": ref.source_id,
                "label": "Unsupported authority reference",
                "locator": None,
                "excerpt": None,
                "verified": False,
            })
    return authorities


async def _active_template(db: AsyncSession, draft_type: str) -> LegalDraftTemplate | None:
    return await db.scalar(
        select(LegalDraftTemplate)
        .where(
            LegalDraftTemplate.code == draft_type,
            LegalDraftTemplate.active.is_(True),
        )
        .order_by(LegalDraftTemplate.version.desc())
    )


async def create_draft(db: AsyncSession, payload: LegalDraftCreate) -> LegalDraft:
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    definition = DRAFT_DEFINITIONS.get(payload.draft_type.value)
    if not definition:
        raise HTTPException(status_code=400, detail="Unsupported draft type")

    context = await _matter_context(
        db,
        payload.matter_id,
        selected_fact_ids=payload.selected_fact_ids,
        selected_event_ids=payload.selected_timeline_event_ids,
    )
    authorities = await _resolve_authorities(db, payload.authority_refs)
    sections, findings = build_sections(
        definition,
        payload.draft_type.value,
        context,
        payload.questionnaire_json,
        authorities,
    )
    template = await _active_template(db, payload.draft_type.value)
    title = payload.title or f"{definition['name_en']} — {context['matter_title']}"
    draft = LegalDraft(
        matter_id=payload.matter_id,
        template_id=template.id if template else None,
        title=title,
        draft_type=payload.draft_type,
        language=payload.language,
        status=LegalDraftStatus.DRAFT,
        court_name=context["court_name"],
        case_number=context["case_number"],
        questionnaire_json=payload.questionnaire_json,
        health_score=health_score(findings),
        metadata_json={
            "selected_fact_ids": [str(value) for value in payload.selected_fact_ids],
            "selected_timeline_event_ids": [str(value) for value in payload.selected_timeline_event_ids],
            "authority_refs": [
                {"source_type": item.source_type.value, "source_id": str(item.source_id)}
                for item in payload.authority_refs
            ],
            "generator": "deterministic_builder_v1",
        },
    )
    db.add(draft)
    await db.flush()

    for item in sections:
        section = LegalDraftSection(
            draft_id=draft.id,
            section_key=item["section_key"],
            title_en=item["title_en"],
            title_hi=item["title_hi"],
            body_en=item["body_en"],
            body_hi=item["body_hi"],
            position=item["position"],
            source=DraftSectionSource.DETERMINISTIC,
            reviewed=False,
            locked=False,
            metadata_json=item["metadata"],
        )
        db.add(section)
        await db.flush()
        for source_item in item["sources"]:
            db.add(LegalDraftSource(
                draft_id=draft.id,
                section_id=section.id,
                source_type=DraftSourceType(source_item["source_type"]),
                source_id=source_item["source_id"],
                label=source_item["label"],
                locator=source_item["locator"],
                excerpt=source_item["excerpt"],
                verified=source_item["verified"],
                metadata_json=source_item["metadata"],
            ))

    for finding in findings:
        db.add(LegalDraftFinding(
            draft_id=draft.id,
            rule_code=finding["rule_code"],
            section_key=finding["section_key"],
            title=finding["title"],
            explanation=finding["explanation"],
            level=DraftFindingLevel(finding["level"]),
            status=DraftFindingStatus(finding["status"]),
            metadata_json=finding["metadata"],
        ))

    await db.commit()
    return await get_draft(db, draft.id)


async def list_drafts(
    db: AsyncSession,
    *,
    matter_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    stmt = select(LegalDraft, Matter).join(Matter, LegalDraft.matter_id == Matter.id)
    actor = get_current_actor()
    if actor is not None:
        visible = await visible_matter_ids(db, actor)
        if not visible:
            return []
        stmt = stmt.where(LegalDraft.matter_id.in_(visible))
    if matter_id:
        stmt = stmt.where(LegalDraft.matter_id == matter_id)
    rows = (await db.execute(
        stmt.options(*_draft_options()).order_by(LegalDraft.updated_at.desc()).offset(offset).limit(limit)
    )).all()
    output = []
    for draft, matter in rows:
        output.append({
            "id": draft.id,
            "matter_id": draft.matter_id,
            "matter_title": matter.title,
            "title": draft.title,
            "draft_type": draft.draft_type,
            "language": draft.language,
            "status": draft.status,
            "health_score": draft.health_score,
            "open_high_findings": sum(
                1 for finding in draft.findings
                if finding.level == DraftFindingLevel.HIGH and finding.status == DraftFindingStatus.OPEN
            ),
            "reviewed_sections": sum(1 for section in draft.sections if section.reviewed),
            "section_count": len(draft.sections),
            "updated_at": draft.updated_at,
        })
    return output


async def _require_draft_work(db: AsyncSession, draft: LegalDraft) -> None:
    actor = get_current_actor()
    if actor is None:
        return
    decision = await decide_matter_access(db, actor, draft.matter_id, required=MatterAccessLevel.WORK)
    if not decision.allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)


async def update_draft(db: AsyncSession, draft_id: UUID, payload: LegalDraftUpdate) -> LegalDraft:
    draft = await get_draft(db, draft_id)
    await _require_draft_work(db, draft)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(draft, key, value)
    if "questionnaire_json" in values:
        draft.status = LegalDraftStatus.DRAFT
    await db.commit()
    return await get_draft(db, draft_id)


async def regenerate_draft(db: AsyncSession, draft_id: UUID) -> LegalDraft:
    draft = await get_draft(db, draft_id)
    await _require_draft_work(db, draft)
    definition = DRAFT_DEFINITIONS[draft.draft_type.value]
    metadata = draft.metadata_json or {}
    selected_fact_ids = [UUID(value) for value in metadata.get("selected_fact_ids", [])]
    selected_event_ids = [UUID(value) for value in metadata.get("selected_timeline_event_ids", [])]
    context = await _matter_context(
        db,
        draft.matter_id,
        selected_fact_ids=selected_fact_ids,
        selected_event_ids=selected_event_ids,
    )

    class Ref:
        def __init__(self, source_type: str, source_id: str):
            self.source_type = DraftSourceType(source_type)
            self.source_id = UUID(source_id)

    refs = [Ref(item["source_type"], item["source_id"]) for item in metadata.get("authority_refs", [])]
    authorities = await _resolve_authorities(db, refs)
    sections, findings = build_sections(
        definition,
        draft.draft_type.value,
        context,
        draft.questionnaire_json or {},
        authorities,
    )
    by_key = {section.section_key: section for section in draft.sections}
    for item in sections:
        section = by_key.get(item["section_key"])
        if section and section.locked:
            continue
        if section is None:
            section = LegalDraftSection(
                draft_id=draft.id,
                section_key=item["section_key"],
                title_en=item["title_en"],
                title_hi=item["title_hi"],
                body_en=item["body_en"],
                body_hi=item["body_hi"],
                position=item["position"],
                source=DraftSectionSource.DETERMINISTIC,
                reviewed=False,
                locked=False,
                metadata_json=item["metadata"],
            )
            db.add(section)
            await db.flush()
        else:
            section.title_en = item["title_en"]
            section.title_hi = item["title_hi"]
            section.body_en = item["body_en"]
            section.body_hi = item["body_hi"]
            section.position = item["position"]
            section.source = DraftSectionSource.DETERMINISTIC
            section.reviewed = False
            section.metadata_json = item["metadata"]
            await db.execute(delete(LegalDraftSource).where(LegalDraftSource.section_id == section.id))
        for source_item in item["sources"]:
            db.add(LegalDraftSource(
                draft_id=draft.id,
                section_id=section.id,
                source_type=DraftSourceType(source_item["source_type"]),
                source_id=source_item["source_id"],
                label=source_item["label"],
                locator=source_item["locator"],
                excerpt=source_item["excerpt"],
                verified=source_item["verified"],
                metadata_json=source_item["metadata"],
            ))

    await db.execute(delete(LegalDraftFinding).where(LegalDraftFinding.draft_id == draft.id))
    for finding in findings:
        db.add(LegalDraftFinding(
            draft_id=draft.id,
            rule_code=finding["rule_code"],
            section_key=finding["section_key"],
            title=finding["title"],
            explanation=finding["explanation"],
            level=DraftFindingLevel(finding["level"]),
            status=DraftFindingStatus(finding["status"]),
            metadata_json=finding["metadata"],
        ))
    draft.health_score = health_score(findings)
    draft.status = LegalDraftStatus.DRAFT
    draft.court_name = context["court_name"]
    draft.case_number = context["case_number"]
    await db.commit()
    return await get_draft(db, draft.id)


async def update_section(db: AsyncSession, draft_id: UUID, section_id: UUID, payload) -> LegalDraft:
    draft = await get_draft(db, draft_id)
    await _require_draft_work(db, draft)
    section = next((item for item in draft.sections if item.id == section_id), None)
    if not section:
        raise HTTPException(status_code=404, detail="Draft section not found")
    values = payload.model_dump(exclude_unset=True)
    text_changed = any(key in values for key in {"title_en", "title_hi", "body_en", "body_hi"})
    for key, value in values.items():
        setattr(section, key, value)
    if text_changed:
        section.source = DraftSectionSource.MANUAL
        if "reviewed" not in values:
            section.reviewed = False
        section.metadata_json = {**(section.metadata_json or {}), "manually_edited": True}
    draft.status = LegalDraftStatus.DRAFT
    await db.commit()
    return await get_draft(db, draft_id)


async def update_finding(db: AsyncSession, draft_id: UUID, finding_id: UUID, new_status) -> LegalDraft:
    draft = await get_draft(db, draft_id)
    await _require_draft_work(db, draft)
    finding = next((item for item in draft.findings if item.id == finding_id), None)
    if not finding:
        raise HTTPException(status_code=404, detail="Draft finding not found")
    finding.status = new_status
    draft.health_score = health_score([
        {"level": item.level.value, "status": (new_status.value if item.id == finding_id else item.status.value)}
        for item in draft.findings
    ])
    await db.commit()
    return await get_draft(db, draft_id)


def _snapshot(draft: LegalDraft) -> tuple[list, list, list]:
    sections = [{
        "id": str(section.id),
        "section_key": section.section_key,
        "title_en": section.title_en,
        "title_hi": section.title_hi,
        "body_en": section.body_en,
        "body_hi": section.body_hi,
        "position": section.position,
        "source": section.source.value,
        "reviewed": section.reviewed,
        "locked": section.locked,
    } for section in draft.sections]
    findings = [{
        "id": str(item.id),
        "rule_code": item.rule_code,
        "title": item.title,
        "level": item.level.value,
        "status": item.status.value,
    } for item in draft.findings]
    sources = [{
        "section_id": str(section.id),
        "source_type": source.source_type.value,
        "source_id": str(source.source_id) if source.source_id else None,
        "label": source.label,
        "locator": source.locator,
        "verified": source.verified,
    } for section in draft.sections for source in section.sources]
    return sections, findings, sources


async def render_draft(db: AsyncSession, draft_id: UUID, *, label: str = "Draft") -> tuple[LegalDraft, LegalDraftVersion]:
    draft = await get_draft(db, draft_id)
    await _require_draft_work(db, draft)
    max_version = await db.scalar(
        select(func.max(LegalDraftVersion.version_number)).where(LegalDraftVersion.draft_id == draft.id)
    )
    version_number = int(max_version or 0) + 1
    filename, storage_key, digest = await asyncio.to_thread(
        generate_docx, draft, version_number=version_number
    )
    draft.generated_filename = filename
    draft.generated_storage_key = storage_key
    sections, findings, sources = _snapshot(draft)
    version = LegalDraftVersion(
        draft_id=draft.id,
        version_number=version_number,
        label=label,
        sections_json=sections,
        findings_json=findings,
        sources_json=sources,
        health_score=draft.health_score,
        sha256=digest,
        generated_filename=filename,
        generated_storage_key=storage_key,
    )
    db.add(version)
    await db.commit()
    return await get_draft(db, draft.id), version


async def begin_review(db: AsyncSession, draft_id: UUID) -> LegalDraft:
    draft = await get_draft(db, draft_id)
    await _require_draft_work(db, draft)
    draft.status = LegalDraftStatus.IN_REVIEW
    await db.commit()
    return await get_draft(db, draft_id)


async def approve_draft(db: AsyncSession, draft_id: UUID) -> tuple[LegalDraft, LegalDraftVersion]:
    draft = await get_draft(db, draft_id)
    await _require_draft_work(db, draft)
    open_high = [
        item for item in draft.findings
        if item.level == DraftFindingLevel.HIGH and item.status == DraftFindingStatus.OPEN
    ]
    if open_high:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Resolve or explicitly accept all high-priority drafting findings before approval.",
                "open_high_findings": [item.rule_code for item in open_high],
            },
        )
    unreviewed = [item for item in draft.sections if not item.reviewed]
    if unreviewed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Every section must be reviewed before approval.",
                "unreviewed_sections": [item.section_key for item in unreviewed],
            },
        )
    draft.status = LegalDraftStatus.APPROVED
    draft.approved_at = datetime.now(timezone.utc)
    await db.commit()
    return await render_draft(db, draft_id, label="Approved")


async def list_versions(db: AsyncSession, draft_id: UUID) -> list[LegalDraftVersion]:
    await get_draft(db, draft_id)
    return list((await db.scalars(
        select(LegalDraftVersion)
        .where(LegalDraftVersion.draft_id == draft_id)
        .order_by(LegalDraftVersion.version_number.desc())
    )).all())


async def get_download_path(db: AsyncSession, draft_id: UUID) -> tuple[LegalDraft, Path]:
    draft = await get_draft(db, draft_id)
    if not draft.generated_storage_key:
        raise HTTPException(status_code=404, detail="No rendered DOCX exists for this draft")
    path = resolve_draft_storage_key(draft.generated_storage_key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Rendered DOCX file is missing")
    return draft, path
