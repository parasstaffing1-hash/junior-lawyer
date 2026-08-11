from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice
from app.models.contract import Contract
from app.models.crm import Client, ClientCommunication, CRMTask
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.drafting import LegalDraft
from app.models.evidence import EvidenceItem, EvidenceWitness
from app.models.intelligence import MatterFact
from app.models.knowledge import KnowledgeAsset, KnowledgeAssetStatus
from app.models.legal_corpus import Judgment, JudgmentParagraph, Statute, StatuteSection
from app.models.matter import Matter
from app.models.operations import WorkflowTask
from app.models.procedure import Hearing, MatterDeadline
from app.models.search import RecentItem, SavedSearch, SearchEntityType, SearchPreference
from app.models.security import OrganizationRole
from app.schemas.search import RecentItemCreate, SavedSearchCreate
from app.services.billing.service import _visible_billing_client_ids
from app.services.research.ranking import expand_query
from app.services.search.ranking import SearchCandidate, rank_candidates
from app.services.security.context import ActorContext
from app.services.security.permissions import decide_client_access, decide_matter_access, visible_client_ids, visible_matter_ids


LEGAL_WORKSPACE_ROLES = {
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.PARTNER,
    OrganizationRole.LAWYER,
    OrganizationRole.JUNIOR,
    OrganizationRole.PARALEGAL,
    OrganizationRole.READ_ONLY,
}

ALL_SCOPES = set(SearchEntityType)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value) -> str:
    return getattr(value, "value", str(value))


def _patterns(query: str) -> list[str]:
    normalized, terms = expand_query(query)
    raw = [normalized, *terms]
    seen: set[str] = set()
    patterns: list[str] = []
    for item in raw:
        item = " ".join((item or "").split()).strip()
        if len(item) < 2 or item.casefold() in seen:
            continue
        seen.add(item.casefold())
        patterns.append(f"%{item}%")
    return patterns[:20]


def _text_match(columns, patterns: list[str]):
    return or_(*(column.ilike(pattern) for column in columns for pattern in patterns))


def _candidate(
    entity_type: SearchEntityType,
    entity_id,
    title: str,
    *,
    subtitle: str | None = None,
    text: str = "",
    href: str,
    badges: list[str] | None = None,
    matter_id=None,
    client_id=None,
    metadata: dict | None = None,
) -> SearchCandidate:
    return SearchCandidate(
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        subtitle=subtitle,
        searchable_text=text,
        href=href,
        badges=badges or [],
        matter_id=matter_id,
        client_id=client_id,
        metadata=metadata or {},
    )


async def _matter_titles(db: AsyncSession, ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(Matter.id, Matter.title).where(Matter.id.in_(ids)))).all()
    return dict(rows)


async def universal_search(
    db: AsyncSession,
    actor: ActorContext,
    query: str,
    *,
    scopes: set[SearchEntityType] | None = None,
    limit: int = 30,
    include_corpus: bool = True,
) -> dict:
    # Batch 19: use the permission-aware materialized search index when it has data.
    # The Batch-18 direct-query implementation remains as a safe development/bootstrap fallback.
    from app.services.search_index.service import indexed_search
    indexed = await indexed_search(db, actor, query, scopes=scopes, limit=limit, include_corpus=include_corpus)
    if indexed is not None:
        return indexed
    query = " ".join(query.split()).strip()
    if not query:
        return {"query": query, "normalized_query": "", "expanded_terms": [], "result_count": 0, "results": [], "groups": []}
    scopes = scopes or ALL_SCOPES
    patterns = _patterns(query)
    if not patterns:
        return {"query": query, "normalized_query": query, "expanded_terms": [], "result_count": 0, "results": [], "groups": []}

    visible_matters = await visible_matter_ids(db, actor)
    visible_clients = await visible_client_ids(db, actor)
    matter_titles = await _matter_titles(db, visible_matters)
    candidates: list[SearchCandidate] = []
    per_scope = max(20, min(80, limit * 3))

    if SearchEntityType.MATTER in scopes and visible_matters:
        rows = (await db.scalars(select(Matter).where(Matter.id.in_(visible_matters), _text_match([
            Matter.title, Matter.reference_number, Matter.client_name, Matter.case_number, Matter.cnr_number, Matter.court_name, Matter.description
        ], patterns)).limit(per_scope))).all()
        for row in rows:
            subtitle = " · ".join(x for x in [row.reference_number, row.client_name, row.case_number] if x)
            candidates.append(_candidate(SearchEntityType.MATTER, row.id, row.title, subtitle=subtitle or None,
                text=f"{row.court_name or ''} {row.cnr_number or ''} {row.description or ''}", href=f"/matters/{row.id}",
                badges=[_enum_value(row.status), row.primary_language.value], matter_id=row.id))

    if SearchEntityType.CLIENT in scopes and visible_clients:
        rows = (await db.scalars(select(Client).where(Client.id.in_(visible_clients), _text_match([
            Client.display_name, Client.legal_name, Client.client_number, Client.email, Client.phone
        ], patterns)).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.CLIENT, row.id, row.display_name,
                subtitle=" · ".join(x for x in [row.client_number, row.legal_name] if x) or None,
                text=f"{row.email or ''} {row.phone or ''} {row.city or ''} {row.state or ''}", href=f"/clients?client={row.id}",
                badges=[_enum_value(row.status), _enum_value(row.client_type)], client_id=row.id))

    if SearchEntityType.DOCUMENT in scopes and visible_matters:
        rows = (await db.execute(select(Document, DocumentPage).outerjoin(DocumentPage, DocumentPage.document_id == Document.id)
            .where(Document.matter_id.in_(visible_matters), _text_match([Document.filename, Document.display_name, DocumentPage.text], patterns))
            .order_by(DocumentPage.page_number).limit(per_scope))).all()
        seen_docs: set[UUID] = set()
        for doc, page in rows:
            if doc.id in seen_docs:
                continue
            seen_docs.add(doc.id)
            title = doc.display_name or doc.filename
            page_number = page.page_number if page else None
            page_text = page.text if page else ''
            page_suffix = f' · page {page_number}' if page_number else ''
            page_query = f'&page={page_number}' if page_number else ''
            candidates.append(_candidate(SearchEntityType.DOCUMENT, doc.id, title,
                subtitle=f"{matter_titles.get(doc.matter_id, 'Matter')}{page_suffix}", text=page_text,
                href=f"/documents/{doc.id}?page={page_number or 1}",
                badges=[doc.detected_language.value, doc.extraction_method.value], matter_id=doc.matter_id,
                metadata={"page_number": page_number}))

    if SearchEntityType.FACT in scopes and visible_matters:
        rows = (await db.scalars(select(MatterFact).where(MatterFact.matter_id.in_(visible_matters), _text_match([
            MatterFact.label, MatterFact.value_text, MatterFact.normalized_value, MatterFact.category
        ], patterns)).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.FACT, row.id, row.label,
                subtitle=matter_titles.get(row.matter_id), text=row.value_text,
                href=f"/matters/{row.matter_id}?tab=facts&fact={row.id}", badges=[row.category, _enum_value(row.status)], matter_id=row.matter_id))

    if SearchEntityType.EVIDENCE in scopes and visible_matters:
        rows = (await db.scalars(select(EvidenceItem).where(EvidenceItem.matter_id.in_(visible_matters), _text_match([
            EvidenceItem.title, EvidenceItem.summary
        ], patterns)).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.EVIDENCE, row.id, row.title, subtitle=matter_titles.get(row.matter_id),
                text=row.summary or "", href=f"/evidence?matter={row.matter_id}&item={row.id}",
                badges=[_enum_value(row.kind), _enum_value(row.review_status)], matter_id=row.matter_id))

    if SearchEntityType.WITNESS in scopes and visible_matters:
        rows = (await db.scalars(select(EvidenceWitness).where(EvidenceWitness.matter_id.in_(visible_matters), _text_match([
            EvidenceWitness.name, EvidenceWitness.normalized_name, EvidenceWitness.role, EvidenceWitness.notes
        ], patterns)).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.WITNESS, row.id, row.name, subtitle=matter_titles.get(row.matter_id),
                text=f"{row.role or ''} {row.notes or ''}", href=f"/evidence?matter={row.matter_id}&tab=witnesses&witness={row.id}",
                badges=[_enum_value(row.kind), row.side or ""], matter_id=row.matter_id))

    if SearchEntityType.CONTRACT in scopes and actor.role in LEGAL_WORKSPACE_ROLES:
        condition = Contract.organization_id == actor.organization_id
        if visible_matters:
            condition = or_(Contract.matter_id.in_(visible_matters), Contract.matter_id.is_(None))
        else:
            condition = Contract.matter_id.is_(None)
        rows = (await db.scalars(select(Contract).where(Contract.organization_id == actor.organization_id, condition, _text_match([
            Contract.title, Contract.party_a_name, Contract.party_b_name, Contract.jurisdiction
        ], patterns)).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.CONTRACT, row.id, row.title,
                subtitle=f"{row.party_a_name} ↔ {row.party_b_name}", text=f"{row.contract_type.value} {row.jurisdiction}",
                href=f"/contracts?contract={row.id}", badges=[row.contract_type.value, row.status.value], matter_id=row.matter_id))

    if SearchEntityType.DRAFT in scopes and visible_matters:
        rows = (await db.scalars(select(LegalDraft).where(LegalDraft.matter_id.in_(visible_matters), _text_match([
            LegalDraft.title, LegalDraft.court_name, LegalDraft.case_number
        ], patterns)).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.DRAFT, row.id, row.title, subtitle=matter_titles.get(row.matter_id),
                text=f"{row.draft_type.value} {row.court_name or ''} {row.case_number or ''}", href=f"/drafting?draft={row.id}",
                badges=[row.draft_type.value, row.status.value], matter_id=row.matter_id))

    if SearchEntityType.DEADLINE in scopes and visible_matters:
        rows = (await db.scalars(select(MatterDeadline).where(MatterDeadline.matter_id.in_(visible_matters), _text_match([
            MatterDeadline.title, MatterDeadline.trigger_type, MatterDeadline.notes
        ], patterns)).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.DEADLINE, row.id, row.title,
                subtitle=f"{matter_titles.get(row.matter_id, 'Matter')} · due {row.due_date.isoformat()}", text=f"{row.trigger_type} {row.notes or ''}",
                href=f"/calendar?matter={row.matter_id}&deadline={row.id}", badges=[row.status.value], matter_id=row.matter_id,
                metadata={"due_date": row.due_date.isoformat()}))

    if SearchEntityType.HEARING in scopes and visible_matters:
        rows = (await db.scalars(select(Hearing).where(Hearing.matter_id.in_(visible_matters), _text_match([
            Hearing.court_name, Hearing.courtroom, Hearing.purpose, Hearing.notes
        ], patterns)).limit(per_scope))).all()
        for row in rows:
            title = row.purpose or "Hearing"
            candidates.append(_candidate(SearchEntityType.HEARING, row.id, title,
                subtitle=f"{matter_titles.get(row.matter_id, 'Matter')} · {row.scheduled_for.isoformat()}", text=f"{row.court_name or ''} {row.courtroom or ''} {row.notes or ''}",
                href=f"/calendar?matter={row.matter_id}&hearing={row.id}", badges=[row.status.value], matter_id=row.matter_id,
                metadata={"scheduled_for": row.scheduled_for.isoformat()}))

    if SearchEntityType.TASK in scopes:
        task_conditions = [WorkflowTask.organization_id == actor.organization_id]
        if visible_matters:
            task_conditions.append(or_(WorkflowTask.matter_id.in_(visible_matters), WorkflowTask.matter_id.is_(None)))
        else:
            task_conditions.append(WorkflowTask.matter_id.is_(None))
        rows = (await db.scalars(select(WorkflowTask).where(*task_conditions, _text_match([WorkflowTask.title, WorkflowTask.description], patterns)).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.TASK, row.id, row.title,
                subtitle=matter_titles.get(row.matter_id) if row.matter_id else "Firm task", text=row.description or "",
                href=f"/operations?task={row.id}", badges=[row.priority.value, row.status.value], matter_id=row.matter_id,
                metadata={"due_at": row.due_at.isoformat() if row.due_at else None}))
        crm_conditions = [
            CRMTask.organization_id == actor.organization_id,
            or_(CRMTask.client_id.is_(None), CRMTask.client_id.in_(visible_clients)) if visible_clients else CRMTask.client_id.is_(None),
            or_(CRMTask.matter_id.is_(None), CRMTask.matter_id.in_(visible_matters)) if visible_matters else CRMTask.matter_id.is_(None),
        ]
        crm_rows = (await db.scalars(select(CRMTask).where(*crm_conditions, _text_match([CRMTask.title, CRMTask.description], patterns)).limit(per_scope))).all()
        for row in crm_rows:
            candidates.append(_candidate(SearchEntityType.TASK, row.id, row.title,
                subtitle=matter_titles.get(row.matter_id) if row.matter_id else "Client task", text=row.description or "",
                href=f"/clients?task={row.id}", badges=[row.priority.value, row.status.value], matter_id=row.matter_id, client_id=row.client_id))

    if SearchEntityType.INVOICE in scopes and actor.role in {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER, OrganizationRole.LAWYER, OrganizationRole.BILLING}:
        billing_clients = await _visible_billing_client_ids(db, actor)
        if billing_clients:
            rows = (await db.scalars(select(Invoice).where(Invoice.organization_id == actor.organization_id, Invoice.client_id.in_(billing_clients), _text_match([
                Invoice.invoice_number, Invoice.client_name, Invoice.supplier_name, Invoice.place_of_supply, Invoice.irn
            ], patterns)).limit(per_scope))).all()
            for row in rows:
                candidates.append(_candidate(SearchEntityType.INVOICE, row.id, row.invoice_number,
                    subtitle=f"{row.client_name} · {row.currency} {row.grand_total}", text=f"{row.place_of_supply or ''} {row.irn or ''}",
                    href=f"/billing?invoice={row.id}", badges=[row.status.value], matter_id=row.matter_id, client_id=row.client_id,
                    metadata={"amount_due": str(row.amount_due), "due_date": row.due_date.isoformat() if row.due_date else None}))

    if SearchEntityType.COMMUNICATION in scopes and visible_clients:
        visibility = [ClientCommunication.client_id.in_(visible_clients)]
        if visible_matters:
            visibility.append(or_(ClientCommunication.matter_id.in_(visible_matters), ClientCommunication.matter_id.is_(None)))
        else:
            visibility.append(ClientCommunication.matter_id.is_(None))
        rows = (await db.scalars(select(ClientCommunication).where(ClientCommunication.organization_id == actor.organization_id, *visibility,
            _text_match([ClientCommunication.subject, ClientCommunication.summary, ClientCommunication.external_reference], patterns)).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.COMMUNICATION, row.id, row.subject or "Client communication",
                subtitle=f"{row.communication_type.value} · {row.occurred_at.date().isoformat()}", text=row.summary,
                href=f"/clients?client={row.client_id}&communication={row.id}", badges=[row.direction, row.communication_type.value],
                matter_id=row.matter_id, client_id=row.client_id))

    if include_corpus and SearchEntityType.STATUTE in scopes:
        rows = (await db.execute(select(Statute, StatuteSection).join(StatuteSection, StatuteSection.statute_id == Statute.id)
            .where(_text_match([Statute.title_en, Statute.title_hi, Statute.short_title, Statute.act_number, StatuteSection.section_number,
                                StatuteSection.heading_en, StatuteSection.heading_hi, StatuteSection.normalized_text], patterns))
            .limit(per_scope))).all()
        seen: set[UUID] = set()
        for statute, section in rows:
            key = section.id
            if key in seen:
                continue
            seen.add(key)
            heading = section.heading_en or section.heading_hi or f"Section {section.section_number}"
            candidates.append(_candidate(SearchEntityType.STATUTE, section.id,
                f"{statute.short_title or statute.title_en} · {section.provision_type.title()} {section.section_number}",
                subtitle=heading, text=f"{section.text_en or ''} {section.text_hi or ''} {section.normalized_text}",
                href=f"/research?statute={statute.id}&section={section.id}", badges=[statute.jurisdiction, "official corpus"],
                metadata={"statute_id": str(statute.id), "section_number": section.section_number}))

    if include_corpus and SearchEntityType.JUDGMENT in scopes:
        rows = (await db.execute(select(Judgment, JudgmentParagraph).join(JudgmentParagraph, JudgmentParagraph.judgment_id == Judgment.id)
            .where(_text_match([Judgment.case_title, Judgment.case_number, Judgment.neutral_citation, Judgment.court_name,
                                Judgment.normalized_text, JudgmentParagraph.normalized_text, JudgmentParagraph.text], patterns))
            .limit(per_scope))).all()
        seen_judgments: set[UUID] = set()
        for judgment, paragraph in rows:
            if judgment.id in seen_judgments:
                continue
            seen_judgments.add(judgment.id)
            cite_raw = judgment.neutral_citation or (judgment.reported_citations_json[0] if judgment.reported_citations_json else None)
            cite = str(cite_raw) if cite_raw else None
            candidates.append(_candidate(SearchEntityType.JUDGMENT, judgment.id, judgment.case_title,
                subtitle=" · ".join(x for x in [judgment.court_name, cite, judgment.decision_date.isoformat() if judgment.decision_date else None] if x),
                text=paragraph.text, href=f"/research?judgment={judgment.id}&paragraph={paragraph.id}",
                badges=[judgment.court_level.value, "verified corpus"], metadata={"paragraph_number": paragraph.paragraph_number}))

    if SearchEntityType.PRECEDENT in scopes:
        rows = (await db.scalars(select(KnowledgeAsset).where(
            KnowledgeAsset.organization_id == actor.organization_id,
            KnowledgeAsset.status == KnowledgeAssetStatus.APPROVED,
            _text_match([KnowledgeAsset.title, KnowledgeAsset.summary, KnowledgeAsset.search_text, KnowledgeAsset.practice_area, KnowledgeAsset.matter_type], patterns),
        ).limit(per_scope))).all()
        for row in rows:
            candidates.append(_candidate(SearchEntityType.PRECEDENT, row.id, row.title,
                subtitle=" · ".join(x for x in [row.practice_area, row.matter_type] if x) or None,
                text=f"{row.summary or ''} {row.search_text}", href=f"/knowledge?asset={row.id}",
                badges=[row.kind.value, row.language.value, "approved"], metadata={"quality_score": row.quality_score}))

    normalized, terms, ranked = rank_candidates(query, candidates, limit=limit)
    results = []
    groups: dict[SearchEntityType, list[dict]] = defaultdict(list)
    for item in ranked:
        c = item.candidate
        out = {
            "entity_type": c.entity_type,
            "entity_id": c.entity_id,
            "title": c.title,
            "subtitle": c.subtitle,
            "snippet": item.snippet,
            "href": c.href,
            "score": round(item.score, 4),
            "badges": [badge for badge in c.badges if badge],
            "matter_id": c.matter_id,
            "client_id": c.client_id,
            "metadata": c.metadata or {},
        }
        results.append(out)
        groups[c.entity_type].append(out)
    return {
        "query": query,
        "normalized_query": normalized,
        "expanded_terms": terms,
        "result_count": len(results),
        "groups": [{"entity_type": key, "count": len(value), "results": value} for key, value in groups.items()],
        "results": results,
    }


async def get_preferences(db: AsyncSession, actor: ActorContext) -> SearchPreference:
    row = await db.scalar(select(SearchPreference).where(SearchPreference.membership_id == actor.membership_id))
    if row:
        return row
    row = SearchPreference(organization_id=actor.organization_id, membership_id=actor.membership_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_preferences(db: AsyncSession, actor: ActorContext, data: dict) -> SearchPreference:
    row = await get_preferences(db, actor)
    for key, value in data.items():
        if value is not None:
            setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


async def list_saved_searches(db: AsyncSession, actor: ActorContext) -> list[SavedSearch]:
    return list((await db.scalars(select(SavedSearch).where(
        SavedSearch.organization_id == actor.organization_id,
        SavedSearch.membership_id == actor.membership_id,
    ).order_by(SavedSearch.pinned.desc(), SavedSearch.updated_at.desc()))).all())


async def create_saved_search(db: AsyncSession, actor: ActorContext, payload: SavedSearchCreate) -> SavedSearch:
    row = SavedSearch(
        organization_id=actor.organization_id,
        membership_id=actor.membership_id,
        name=payload.name.strip(),
        query=payload.query.strip(),
        scopes_json=[scope.value for scope in payload.scopes],
        filters_json=payload.filters,
        pinned=payload.pinned,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def mark_saved_search_run(db: AsyncSession, actor: ActorContext, search_id: UUID) -> SavedSearch:
    row = await db.get(SavedSearch, search_id)
    if not row or row.organization_id != actor.organization_id or row.membership_id != actor.membership_id:
        raise HTTPException(404, "Saved search not found")
    row.last_run_at = _now()
    await db.commit()
    await db.refresh(row)
    return row


async def delete_saved_search(db: AsyncSession, actor: ActorContext, search_id: UUID) -> None:
    row = await db.get(SavedSearch, search_id)
    if not row or row.organization_id != actor.organization_id or row.membership_id != actor.membership_id:
        raise HTTPException(404, "Saved search not found")
    await db.delete(row)
    await db.commit()


async def record_recent(db: AsyncSession, actor: ActorContext, payload: RecentItemCreate) -> RecentItem:
    if payload.matter_id:
        decision = await decide_matter_access(db, actor, payload.matter_id)
        if not decision.allowed:
            raise HTTPException(403, decision.reason)
    if payload.client_id:
        decision = await decide_client_access(db, actor, payload.client_id)
        if not decision.allowed:
            raise HTTPException(403, decision.reason)
    row = await db.scalar(select(RecentItem).where(
        RecentItem.membership_id == actor.membership_id,
        RecentItem.entity_type == payload.entity_type,
        RecentItem.entity_id == payload.entity_id,
    ))
    if not row:
        row = RecentItem(
            organization_id=actor.organization_id,
            membership_id=actor.membership_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            title_snapshot=payload.title,
            subtitle_snapshot=payload.subtitle,
            href=payload.href,
            matter_id=payload.matter_id,
            client_id=payload.client_id,
            opened_at=_now(),
            open_count=1,
        )
        db.add(row)
    else:
        row.title_snapshot = payload.title
        row.subtitle_snapshot = payload.subtitle
        row.href = payload.href
        row.matter_id = payload.matter_id
        row.client_id = payload.client_id
        row.opened_at = _now()
        row.open_count += 1
    await db.commit()
    await db.refresh(row)
    return row


async def list_recent(db: AsyncSession, actor: ActorContext, limit: int = 12) -> list[RecentItem]:
    rows = list((await db.scalars(select(RecentItem).where(
        RecentItem.organization_id == actor.organization_id,
        RecentItem.membership_id == actor.membership_id,
    ).order_by(RecentItem.opened_at.desc()).limit(limit * 3))).all())
    visible: list[RecentItem] = []
    for row in rows:
        if row.matter_id and not (await decide_matter_access(db, actor, row.matter_id)).allowed:
            continue
        if row.client_id and not (await decide_client_access(db, actor, row.client_id)).allowed:
            continue
        visible.append(row)
        if len(visible) >= limit:
            break
    return visible


COMMANDS = [
    {"id": "go-onboarding", "title": "Getting started", "description": "Workspace preferences, first matter and keyboard workflow", "keywords": ["onboarding", "getting started", "preferences", "accessibility", "शुरुआत", "सेटिंग"], "href": "/onboarding", "shortcut": "G ?", "write_action": False},
    {"id": "go-matters", "title": "Go to Matters", "description": "Open the matter workspace", "keywords": ["matter", "case", "मामला"], "href": "/matters", "shortcut": "G M", "write_action": False},
    {"id": "go-cases", "title": "Case Lookup", "description": "Search an official/saved case by CNR or case number", "keywords": ["case lookup", "cnr", "case number", "court case", "केस खोज", "मामला नंबर"], "href": "/cases", "shortcut": "G S", "write_action": False},
    {"id": "new-matter", "title": "Create a matter", "description": "Start a new legal matter", "keywords": ["new matter", "create case", "नया मामला"], "href": "/matters?new=1", "shortcut": "N M", "write_action": True},
    {"id": "go-research", "title": "Legal research", "description": "Search statutes, sections and judgments", "keywords": ["research", "judgment", "statute", "कानून", "निर्णय"], "href": "/research", "shortcut": "G R", "write_action": False},
    {"id": "new-contract", "title": "Draft a contract", "description": "Open deterministic contract drafting", "keywords": ["contract", "agreement", "अनुबंध", "समझौता"], "href": "/contracts?new=1", "shortcut": "N C", "write_action": True},
    {"id": "new-draft", "title": "Create legal draft", "description": "Open the litigation drafting studio", "keywords": ["draft", "petition", "notice", "याचिका", "नोटिस"], "href": "/drafting?new=1", "shortcut": "N D", "write_action": True},
    {"id": "go-evidence", "title": "Evidence workspace", "description": "Issues, witnesses, evidence and bundles", "keywords": ["evidence", "witness", "साक्ष्य", "गवाह"], "href": "/evidence", "shortcut": "G E", "write_action": False},
    {"id": "go-calendar", "title": "Calendar & deadlines", "description": "Hearings, deadlines and procedure", "keywords": ["calendar", "deadline", "hearing", "तारीख", "सुनवाई"], "href": "/calendar", "shortcut": "G C", "write_action": False},
    {"id": "go-operations", "title": "Operations", "description": "Tasks, court changes and daily agenda", "keywords": ["task", "operations", "court update", "कार्य"], "href": "/operations", "shortcut": "G O", "write_action": False},
    {"id": "go-clients", "title": "Clients", "description": "CRM, intake and conflict checks", "keywords": ["client", "crm", "conflict", "मुवक्किल"], "href": "/clients", "shortcut": "G L", "write_action": False},
    {"id": "go-knowledge", "title": "Firm knowledge", "description": "Approved precedents and playbooks", "keywords": ["precedent", "knowledge", "playbook", "नज़ीर"], "href": "/knowledge", "shortcut": "G K", "write_action": False},
    {"id": "go-billing", "title": "Billing", "description": "Invoices, collections and statements", "keywords": ["billing", "invoice", "payment", "बिल"], "href": "/billing", "shortcut": "G B", "write_action": False},
    {"id": "go-analytics", "title": "Analytics", "description": "Matter health and supervision signals", "keywords": ["analytics", "health", "risk", "dashboard"], "href": "/analytics", "shortcut": "G A", "write_action": False},
    {"id": "go-jobs", "title": "Background jobs", "description": "OCR, indexing and large processing queues", "keywords": ["jobs", "queue", "worker", "ocr", "indexing", "प्रोसेसिंग"], "href": "/jobs", "shortcut": "G J", "write_action": False},
    {"id": "go-system-health", "title": "System health", "description": "Reliability, incidents, backups and restore verification", "keywords": ["system health", "backup", "restore", "incident", "recovery", "स्वास्थ्य", "बैकअप"], "href": "/system-health", "shortcut": "G H", "write_action": False},
    {"id": "go-qa", "title": "Quality assurance", "description": "Golden legal cases and release quality gates", "keywords": ["qa", "quality", "testing", "release gate", "legal accuracy", "security tests", "citation tests", "गुणवत्ता", "परीक्षण"], "href": "/qa", "shortcut": "G Q", "write_action": False},
    {"id": "go-release", "title": "Release engineering", "description": "CI gates, load tests, security tests and deployment approval", "keywords": ["release", "deployment", "load test", "stress", "security gate", "rollback", "रिलीज", "परीक्षण"], "href": "/release", "shortcut": "G X", "write_action": False},
    {"id": "go-validation", "title": "Release candidate validation", "description": "Staging, recovery, authenticated security, scale and pilot-readiness evidence", "keywords": ["rc", "release candidate", "validation", "staging", "pilot", "e2e", "security", "recovery", "सत्यापन", "पायलट"], "href": "/validation", "shortcut": "G V", "write_action": False},
    {"id": "go-deployment", "title": "Production deployment", "description": "Topology, readiness, rollouts and runtime controls", "keywords": ["deployment", "production", "docker", "tls", "object storage", "rollout", "तैनाती"], "href": "/deployment", "shortcut": "G P", "write_action": False},
    {"id": "go-integrations", "title": "Integrations", "description": "Email, calendar, payments, e-signature and data connectors", "keywords": ["integrations", "gmail", "calendar", "razorpay", "docusign", "webhook", "एकीकरण", "कैलेंडर"], "href": "/integrations", "shortcut": "G I", "write_action": False},
    {"id": "go-legal-data", "title": "Legal data operations", "description": "Official corpus feeds, statute changes, integrity and jurisdiction packs", "keywords": ["legal data", "corpus", "statute update", "amendment", "judgment import", "कानूनी डेटा", "संशोधन"], "href": "/legal-data", "shortcut": "G D", "write_action": False},
]


def list_commands(query: str | None = None) -> list[dict]:
    if not query:
        return COMMANDS
    normalized, terms = expand_query(query)
    needle = {normalized.casefold(), *(term.casefold() for term in terms)}
    out = []
    for command in COMMANDS:
        hay = " ".join([command["title"], command["description"], *command["keywords"]]).casefold()
        if any(term and term in hay for term in needle):
            out.append(command)
    return out
