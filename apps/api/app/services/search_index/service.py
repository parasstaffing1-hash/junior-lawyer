from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select
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
from app.models.search import SearchEntityType
from app.models.search_index import (
    DuplicateRelationKind, SearchDuplicateRelation, SearchIndexEntry, SearchIndexHealthSnapshot,
    SearchIndexJob, SearchIndexJobKind, SearchIndexJobStatus, SearchPerformancePreference,
)
from app.services.billing.service import _visible_billing_client_ids
from app.services.language.detector import detect_language
from app.services.language.normalizer import normalize_legal_text
from app.services.research.ranking import bm25_scores, expand_query, make_snippet
from app.services.search.ranking import TYPE_WEIGHT
from app.services.search_index.engine import (
    content_hash, cosine_similarity, duplicate_score, index_document_chunks, simhash64, simhash_bands, tokenize,
)
from app.services.search_index.providers import local_embedding
from app.services.security.context import ActorContext
from app.services.security.permissions import visible_client_ids, visible_matter_ids


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _v(value) -> str:
    return getattr(value, "value", str(value)) if value is not None else ""


def _source_key(org_id: UUID | None, entity_type: SearchEntityType, entity_id: UUID, chunk_key: str) -> str:
    prefix = str(org_id) if org_id else "public"
    return f"{prefix}:{entity_type.value}:{entity_id}:{chunk_key}"


def _compose(*parts) -> str:
    return " ".join(str(part) for part in parts if part is not None and str(part).strip())


async def _put(
    db: AsyncSession, *, organization_id: UUID | None, entity_type: SearchEntityType, entity_id: UUID,
    chunk_key: str, title: str, body: str, href: str, subtitle: str | None = None,
    matter_id: UUID | None = None, client_id: UUID | None = None, badges: list[str] | None = None,
    metadata: dict | None = None, rank_weight: float = 1.0,
) -> tuple[SearchIndexEntry, bool]:
    source_key = _source_key(organization_id, entity_type, entity_id, chunk_key)
    combined = _compose(title, subtitle, body)
    normalized = normalize_legal_text(combined)
    digest = content_hash(combined)
    existing = await db.scalar(select(SearchIndexEntry).where(SearchIndexEntry.source_key == source_key))
    created = existing is None
    row = existing or SearchIndexEntry(source_key=source_key, entity_type=entity_type, entity_id=entity_id, chunk_key=chunk_key)
    row.organization_id = organization_id
    row.entity_type = entity_type
    row.entity_id = entity_id
    row.chunk_key = chunk_key
    row.matter_id = matter_id
    row.client_id = client_id
    row.title = title[:700]
    row.subtitle = subtitle[:1000] if subtitle else None
    row.body_text = body
    row.normalized_text = normalized
    row.language = detect_language(combined).language
    row.href = href
    row.badges_json = badges or []
    row.metadata_json = metadata or {}
    row.content_hash = digest
    row.simhash64 = simhash64(combined)
    row.feature_vector_json = local_embedding(combined, expand_legal=False)
    row.token_count = len(tokenize(combined))
    row.rank_weight = rank_weight
    row.indexed_at = _now()
    row.is_deleted = False
    if created:
        db.add(row)
    return row, created


async def rebuild_organization_index(db: AsyncSession, actor: ActorContext, *, include_corpus: bool = True) -> SearchIndexJob:
    if _v(actor.role) not in {"owner", "admin", "partner"}:
        raise HTTPException(status_code=403, detail="Partner, admin or owner role required to rebuild the firm index")
    job = SearchIndexJob(
        organization_id=actor.organization_id, requested_by_membership_id=actor.membership_id,
        kind=SearchIndexJobKind.ORGANIZATION, status=SearchIndexJobStatus.RUNNING, started_at=_now(),
    )
    db.add(job); await db.flush()
    seen_keys: set[str] = set()
    created = updated = 0

    async def put(**kwargs):
        nonlocal created, updated
        row, was_created = await _put(db, **kwargs)
        seen_keys.add(row.source_key)
        created += int(was_created); updated += int(not was_created)

    org = actor.organization_id
    try:
        matters = (await db.scalars(select(Matter).where(Matter.organization_id == org))).all()
        for r in matters:
            await put(organization_id=org, entity_type=SearchEntityType.MATTER, entity_id=r.id, chunk_key="root",
                title=r.title, subtitle=_compose(r.reference_number, r.client_name, r.case_number),
                body=_compose(r.court_name, r.cnr_number, r.description), href=f"/matters/{r.id}", matter_id=r.id,
                badges=[_v(r.status), _v(r.primary_language)], rank_weight=1.05)

        clients = (await db.scalars(select(Client).where(Client.organization_id == org))).all()
        for r in clients:
            await put(organization_id=org, entity_type=SearchEntityType.CLIENT, entity_id=r.id, chunk_key="root",
                title=r.display_name, subtitle=_compose(r.client_number, r.legal_name), body=_compose(r.email, r.phone, r.city, r.state),
                href=f"/clients?client={r.id}", client_id=r.id, badges=[_v(r.status), _v(r.client_type)], rank_weight=1.03)

        docs = (await db.execute(select(Document, DocumentPage).join(DocumentPage, DocumentPage.document_id == Document.id)
            .join(Matter, Matter.id == Document.matter_id).where(Matter.organization_id == org))).all()
        for doc, page in docs:
            for chunk_no, chunk in index_document_chunks(page.text):
                await put(organization_id=org, entity_type=SearchEntityType.DOCUMENT, entity_id=doc.id,
                    chunk_key=f"p{page.page_number}:c{chunk_no}", title=doc.display_name or doc.filename,
                    subtitle=f"Page {page.page_number}", body=chunk, href=f"/documents/{doc.id}?page={page.page_number}",
                    matter_id=doc.matter_id, badges=[_v(doc.detected_language), _v(doc.extraction_method)],
                    metadata={"page_number": page.page_number, "document_id": str(doc.id)}, rank_weight=1.0)

        facts = (await db.execute(select(MatterFact, Matter).join(Matter, Matter.id == MatterFact.matter_id).where(Matter.organization_id == org))).all()
        for r, matter in facts:
            await put(organization_id=org, entity_type=SearchEntityType.FACT, entity_id=r.id, chunk_key="root", title=r.label,
                subtitle=matter.title, body=_compose(r.value_text, r.normalized_value, r.category), href=f"/matters/{r.matter_id}?tab=facts&fact={r.id}",
                matter_id=r.matter_id, badges=[_v(r.fact_type), _v(r.status)])

        evidence = (await db.execute(select(EvidenceItem, Matter).join(Matter, Matter.id == EvidenceItem.matter_id).where(Matter.organization_id == org))).all()
        for r, matter in evidence:
            await put(organization_id=org, entity_type=SearchEntityType.EVIDENCE, entity_id=r.id, chunk_key="root", title=r.title,
                subtitle=matter.title, body=_compose(r.summary, r.kind, r.strength), href=f"/evidence?matter={r.matter_id}&evidence={r.id}",
                matter_id=r.matter_id, badges=[_v(r.kind), _v(r.review_status)])

        witnesses = (await db.execute(select(EvidenceWitness, Matter).join(Matter, Matter.id == EvidenceWitness.matter_id).where(Matter.organization_id == org))).all()
        for r, matter in witnesses:
            await put(organization_id=org, entity_type=SearchEntityType.WITNESS, entity_id=r.id, chunk_key="root", title=r.name,
                subtitle=_compose(matter.title, r.role), body=_compose(r.normalized_name, r.side, r.notes), href=f"/evidence?matter={r.matter_id}&witness={r.id}",
                matter_id=r.matter_id, badges=[_v(r.kind), r.side or ""])

        contracts = (await db.scalars(select(Contract).where(Contract.organization_id == org))).all()
        for r in contracts:
            await put(organization_id=org, entity_type=SearchEntityType.CONTRACT, entity_id=r.id, chunk_key="root", title=r.title,
                subtitle=_compose(r.party_a_name, "v", r.party_b_name), body=_compose(r.contract_type, r.jurisdiction, r.governing_state, json.dumps(r.questionnaire_json, ensure_ascii=False)),
                href=f"/contracts?contract={r.id}", matter_id=r.matter_id, badges=[_v(r.contract_type), _v(r.status), _v(r.language)])

        drafts = (await db.execute(select(LegalDraft, Matter).join(Matter, Matter.id == LegalDraft.matter_id).where(Matter.organization_id == org))).all()
        for r, matter in drafts:
            body = _compose(r.court_name, r.case_number, json.dumps(r.questionnaire_json, ensure_ascii=False))
            await put(organization_id=org, entity_type=SearchEntityType.DRAFT, entity_id=r.id, chunk_key="root", title=r.title,
                subtitle=matter.title, body=body, href=f"/drafting?draft={r.id}", matter_id=r.matter_id,
                badges=[_v(r.draft_type), _v(r.status), _v(r.language)])

        deadlines = (await db.execute(select(MatterDeadline, Matter).join(Matter, Matter.id == MatterDeadline.matter_id).where(Matter.organization_id == org))).all()
        for r, matter in deadlines:
            await put(organization_id=org, entity_type=SearchEntityType.DEADLINE, entity_id=r.id, chunk_key="root", title=r.title,
                subtitle=f"{matter.title} · due {r.due_date.isoformat()}", body=_compose(r.trigger_type, r.notes, json.dumps(r.authority_json, ensure_ascii=False)),
                href=f"/calendar?matter={r.matter_id}&deadline={r.id}", matter_id=r.matter_id, badges=[_v(r.status)])

        hearings = (await db.execute(select(Hearing, Matter).join(Matter, Matter.id == Hearing.matter_id).where(Matter.organization_id == org))).all()
        for r, matter in hearings:
            await put(organization_id=org, entity_type=SearchEntityType.HEARING, entity_id=r.id, chunk_key="root", title=r.purpose or "Hearing",
                subtitle=_compose(matter.title, r.scheduled_for.isoformat()), body=_compose(r.court_name, r.courtroom, r.judge_or_bench, r.notes),
                href=f"/calendar?matter={r.matter_id}&hearing={r.id}", matter_id=r.matter_id, badges=[_v(r.status)])

        workflow_tasks = (await db.scalars(select(WorkflowTask).where(WorkflowTask.organization_id == org))).all()
        for r in workflow_tasks:
            await put(organization_id=org, entity_type=SearchEntityType.TASK, entity_id=r.id, chunk_key="workflow", title=r.title,
                body=_compose(r.description, r.priority, r.status), href=f"/operations?task={r.id}", matter_id=r.matter_id,
                badges=[_v(r.priority), _v(r.status)])
        crm_tasks = (await db.scalars(select(CRMTask).where(CRMTask.organization_id == org))).all()
        for r in crm_tasks:
            await put(organization_id=org, entity_type=SearchEntityType.TASK, entity_id=r.id, chunk_key="crm", title=r.title,
                body=_compose(r.description, r.priority, r.status), href=f"/clients?task={r.id}", matter_id=r.matter_id, client_id=r.client_id,
                badges=[_v(r.priority), _v(r.status)])

        invoices = (await db.scalars(select(Invoice).where(Invoice.organization_id == org))).all()
        for r in invoices:
            await put(organization_id=org, entity_type=SearchEntityType.INVOICE, entity_id=r.id, chunk_key="root",
                title=r.invoice_number, subtitle=r.client_name, body=_compose(r.status, r.issue_date, r.due_date, r.currency, r.grand_total, r.amount_due),
                href=f"/billing?invoice={r.id}", matter_id=r.matter_id, client_id=r.client_id, badges=[_v(r.status), r.currency])

        precedents = (await db.scalars(select(KnowledgeAsset).where(KnowledgeAsset.organization_id == org, KnowledgeAsset.status == KnowledgeAssetStatus.APPROVED))).all()
        for r in precedents:
            body = _compose(r.summary, r.body_en, r.body_hi, r.search_text)
            for chunk_no, chunk in index_document_chunks(body):
                await put(organization_id=org, entity_type=SearchEntityType.PRECEDENT, entity_id=r.id, chunk_key=f"c{chunk_no}", title=r.title,
                    subtitle=_compose(r.practice_area, r.matter_type), body=chunk, href=f"/knowledge?asset={r.id}",
                    badges=[_v(r.kind), _v(r.language), "approved"], metadata={"quality_score": r.quality_score}, rank_weight=1.02)

        communications = (await db.scalars(select(ClientCommunication).where(ClientCommunication.organization_id == org))).all()
        for r in communications:
            await put(organization_id=org, entity_type=SearchEntityType.COMMUNICATION, entity_id=r.id, chunk_key="root",
                title=r.subject or f"{_v(r.communication_type).title()} communication", subtitle=r.occurred_at.isoformat(),
                body=_compose(r.summary, r.direction, r.external_reference), href=f"/clients?client={r.client_id}&communication={r.id}",
                matter_id=r.matter_id, client_id=r.client_id, badges=[_v(r.communication_type), r.direction])

        if include_corpus:
            statutes = (await db.execute(select(Statute, StatuteSection).join(StatuteSection, StatuteSection.statute_id == Statute.id))).all()
            for statute, section in statutes:
                body = _compose(section.heading_en, section.heading_hi, section.text_en, section.text_hi, section.normalized_text)
                for chunk_no, chunk in index_document_chunks(body):
                    await put(organization_id=None, entity_type=SearchEntityType.STATUTE, entity_id=section.id,
                        chunk_key=f"{section.section_key}:c{chunk_no}", title=f"{statute.short_title or statute.title_en} · {section.provision_type.title()} {section.section_number}",
                        subtitle=section.heading_en or section.heading_hi, body=chunk, href=f"/research?statute={statute.id}&section={section.id}",
                        badges=[statute.jurisdiction, "official corpus"], metadata={"statute_id": str(statute.id), "section_number": section.section_number}, rank_weight=1.03)

            judgments = (await db.execute(select(Judgment, JudgmentParagraph).join(JudgmentParagraph, JudgmentParagraph.judgment_id == Judgment.id))).all()
            for judgment, para in judgments:
                cite = judgment.neutral_citation or (judgment.reported_citations_json[0] if judgment.reported_citations_json else None)
                await put(organization_id=None, entity_type=SearchEntityType.JUDGMENT, entity_id=judgment.id,
                    chunk_key=f"p{para.position}", title=judgment.case_title, subtitle=_compose(judgment.court_name, cite, judgment.decision_date),
                    body=para.text, href=f"/research?judgment={judgment.id}&paragraph={para.id}", badges=[_v(judgment.court_level), "verified corpus"],
                    metadata={"paragraph_id": str(para.id), "paragraph_number": para.paragraph_number}, rank_weight=1.05)

        # Soft-delete stale firm entries. Public corpus is shared and is not deleted by an organization rebuild.
        stale = (await db.scalars(select(SearchIndexEntry).where(SearchIndexEntry.organization_id == org, SearchIndexEntry.is_deleted.is_(False)))).all()
        deleted_count = 0
        for row in stale:
            if row.source_key not in seen_keys:
                row.is_deleted = True; deleted_count += 1

        job.entries_seen = len(seen_keys); job.entries_created = created; job.entries_updated = updated; job.entries_deleted = deleted_count
        job.status = SearchIndexJobStatus.COMPLETED; job.finished_at = _now()
        await db.commit(); await db.refresh(job)
        return job
    except Exception as exc:
        job.status = SearchIndexJobStatus.FAILED; job.error = str(exc)[:5000]; job.finished_at = _now()
        await db.commit()
        raise


async def _preferences(db: AsyncSession, organization_id: UUID) -> SearchPerformancePreference:
    row = await db.scalar(select(SearchPerformancePreference).where(SearchPerformancePreference.organization_id == organization_id))
    if row:
        return row
    row = SearchPerformancePreference(organization_id=organization_id)
    db.add(row); await db.flush()
    return row


async def indexed_search(db: AsyncSession, actor: ActorContext, query: str, *, scopes: set[SearchEntityType] | None = None,
                         limit: int = 30, include_corpus: bool = True) -> dict | None:
    prefs = await _preferences(db, actor.organization_id)
    if not prefs.use_index:
        return None
    base_count = await db.scalar(select(func.count(SearchIndexEntry.id)).where(
        SearchIndexEntry.is_deleted.is_(False), or_(SearchIndexEntry.organization_id == actor.organization_id, SearchIndexEntry.organization_id.is_(None))))
    if not base_count:
        return None

    visible_matters = await visible_matter_ids(db, actor)
    visible_clients = await visible_client_ids(db, actor)
    billing_clients = await _visible_billing_client_ids(db, actor)
    scopes = scopes or set(SearchEntityType)
    expanded_normalized, terms = expand_query(query)
    patterns = [f"%{t}%" for t in terms[:18] if len(t) > 1] or [f"%{expanded_normalized}%"]

    conditions = [SearchIndexEntry.is_deleted.is_(False), SearchIndexEntry.entity_type.in_([x.value for x in scopes])]

    # Security is applied in SQL before the lexical/local-vector ranking stage.
    firm_access = or_(
        # organization-wide sanitized assets / configuration-like search records
        (SearchIndexEntry.organization_id == actor.organization_id) & SearchIndexEntry.matter_id.is_(None) & SearchIndexEntry.client_id.is_(None),
        # explicit client results
        (SearchIndexEntry.organization_id == actor.organization_id) & (SearchIndexEntry.entity_type == SearchEntityType.CLIENT.value) & SearchIndexEntry.client_id.in_(visible_clients or {UUID(int=0)}),
        # billing scope has a distinct permission boundary
        (SearchIndexEntry.organization_id == actor.organization_id) & (SearchIndexEntry.entity_type == SearchEntityType.INVOICE.value) & SearchIndexEntry.client_id.in_(billing_clients or {UUID(int=0)}),
        # normal legal-workspace matter content
        (SearchIndexEntry.organization_id == actor.organization_id) & (SearchIndexEntry.entity_type != SearchEntityType.INVOICE.value) & SearchIndexEntry.matter_id.in_(visible_matters or {UUID(int=0)}),
        # client-only CRM records with no matter link
        (SearchIndexEntry.organization_id == actor.organization_id) & SearchIndexEntry.matter_id.is_(None) & SearchIndexEntry.client_id.in_(visible_clients or {UUID(int=0)}),
    )
    if include_corpus:
        conditions.append(or_(firm_access, SearchIndexEntry.organization_id.is_(None)))
    else:
        conditions.append(firm_access)

    dialect = db.get_bind().dialect.name
    statement = select(SearchIndexEntry).where(*conditions)
    if dialect == "postgresql":
        # PostgreSQL deployments use GIN FTS + pg_trgm preselection created by migration 0018.
        ts_query = func.plainto_tsquery("simple", expanded_normalized)
        ts_vector = func.to_tsvector("simple", SearchIndexEntry.normalized_text)
        trigram = func.similarity(SearchIndexEntry.normalized_text, expanded_normalized)
        statement = statement.where(or_(ts_vector.op("@@")(ts_query), trigram >= 0.08, SearchIndexEntry.title.ilike(f"%{expanded_normalized}%")))
        statement = statement.order_by(func.ts_rank_cd(ts_vector, ts_query).desc(), trigram.desc())
    elif patterns:
        statement = statement.where(or_(*[SearchIndexEntry.normalized_text.ilike(p) for p in patterns], *[SearchIndexEntry.title.ilike(p) for p in patterns]))
    rows = (await db.scalars(statement.limit(max(50, prefs.max_candidate_rows)))).all()
    permitted = rows

    if not permitted:
        return {"query": query, "normalized_query": expanded_normalized, "expanded_terms": terms, "result_count": 0, "results": [], "groups": []}
    docs = [r.normalized_text for r in permitted]
    lexical = bm25_scores(terms, docs)
    qvec = local_embedding(query)
    dedup: dict[tuple[str, UUID], dict] = {}
    for idx, row in enumerate(permitted):
        lex = lexical[idx]
        semantic = cosine_similarity(qvec, row.feature_vector_json or [])
        title_norm = normalize_legal_text(row.title).casefold()
        exact = 1.0 if title_norm == expanded_normalized.casefold() else 0.0
        type_boost = TYPE_WEIGHT.get(SearchEntityType(row.entity_type), 0.85)
        score = lex * prefs.lexical_weight + semantic * prefs.feature_vector_weight + exact * prefs.exact_title_weight + type_boost * prefs.type_weight
        score *= max(0.7, min(1.3, row.rank_weight))
        if score <= 0: continue
        key = (str(row.entity_type), row.entity_id)
        result = {
            "entity_type": _v(row.entity_type), "entity_id": row.entity_id, "title": row.title,
            "subtitle": row.subtitle, "snippet": make_snippet(row.normalized_text, terms, radius=160), "href": row.href,
            "score": min(1.0, round(score, 6)), "badges": row.badges_json or [], "matter_id": row.matter_id,
            "client_id": row.client_id, "metadata": {**(row.metadata_json or {}), "index_chunk": row.chunk_key,
                "lexical_score": round(lex, 4), "local_vector_score": round(semantic, 4)},
        }
        prior = dedup.get(key)
        if prior is None or result["score"] > prior["score"]:
            dedup[key] = result
    results = sorted(dedup.values(), key=lambda r: (r["score"], r["title"].casefold()), reverse=True)[:limit]
    grouped: dict[str, list[dict]] = {}
    for r in results: grouped.setdefault(r["entity_type"], []).append(r)
    return {"query": query, "normalized_query": expanded_normalized, "expanded_terms": terms,
        "result_count": len(results), "results": results,
        "groups": [{"entity_type": k, "count": len(v), "results": v} for k, v in grouped.items()]}


async def detect_duplicates(db: AsyncSession, actor: ActorContext, *, limit: int = 10000) -> int:
    if _v(actor.role) not in {"owner", "admin", "partner"}:
        raise HTTPException(status_code=403, detail="Partner, admin or owner role required")
    prefs = await _preferences(db, actor.organization_id)
    rows = (await db.scalars(select(SearchIndexEntry).where(
        SearchIndexEntry.organization_id == actor.organization_id,
        SearchIndexEntry.entity_type == SearchEntityType.DOCUMENT.value,
        SearchIndexEntry.is_deleted.is_(False), SearchIndexEntry.token_count >= 12,
    ).limit(limit))).all()
    created = 0
    seen_pairs: set[tuple[UUID, UUID]] = set()

    async def add_pair(a: SearchIndexEntry, b: SearchIndexEntry, kind: DuplicateRelationKind, score) -> None:
        nonlocal created
        if a.entity_id == b.entity_id:
            return
        left, right = sorted([a, b], key=lambda x: str(x.id))
        pair = (left.id, right.id)
        if pair in seen_pairs:
            return
        seen_pairs.add(pair)
        exists = await db.scalar(select(SearchDuplicateRelation.id).where(
            SearchDuplicateRelation.left_entry_id == left.id, SearchDuplicateRelation.right_entry_id == right.id))
        if exists:
            return
        db.add(SearchDuplicateRelation(organization_id=actor.organization_id, left_entry_id=left.id, right_entry_id=right.id,
            relation_kind=kind, similarity=score.similarity, hamming_distance=score.hamming, shingle_jaccard=score.jaccard))
        created += 1

    # Exact candidates are O(n) grouped by normalized content hash.
    by_hash: dict[str, list[SearchIndexEntry]] = {}
    for row in rows:
        by_hash.setdefault(row.content_hash, []).append(row)
    for group in by_hash.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if group[i].entity_id == group[j].entity_id:
                    continue
                score = duplicate_score(group[i].body_text, group[j].body_text)
                await add_pair(group[i], group[j], DuplicateRelationKind.EXACT, score)

    # Near candidates use four SimHash LSH bands. Only rows sharing a band are compared.
    buckets: dict[str, list[SearchIndexEntry]] = {}
    for row in rows:
        for band in simhash_bands(row.simhash64):
            buckets.setdefault(band, []).append(row)
    candidate_pairs: set[tuple[UUID, UUID]] = set()
    entry_map = {row.id: row for row in rows}
    for bucket in buckets.values():
        if len(bucket) < 2:
            continue
        # Cap pathological common-text buckets; exact hashes were already handled above.
        bucket = bucket[:250]
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                if bucket[i].entity_id == bucket[j].entity_id or bucket[i].content_hash == bucket[j].content_hash:
                    continue
                left, right = sorted([bucket[i].id, bucket[j].id], key=str)
                candidate_pairs.add((left, right))
    for left_id, right_id in candidate_pairs:
        a, b = entry_map[left_id], entry_map[right_id]
        score = duplicate_score(a.body_text, b.body_text, max_hamming=prefs.near_duplicate_hamming, min_jaccard=prefs.near_duplicate_jaccard)
        if score.near:
            await add_pair(a, b, DuplicateRelationKind.NEAR, score)
    await db.commit()
    return created


async def health(db: AsyncSession, actor: ActorContext) -> dict:
    entries = (await db.scalars(select(SearchIndexEntry).where(
        or_(SearchIndexEntry.organization_id == actor.organization_id, SearchIndexEntry.organization_id.is_(None)),
        SearchIndexEntry.is_deleted.is_(False)))).all()
    by_entity = Counter(_v(r.entity_type) for r in entries)
    exact = await db.scalar(select(func.count(SearchDuplicateRelation.id)).where(
        SearchDuplicateRelation.organization_id == actor.organization_id,
        SearchDuplicateRelation.relation_kind == DuplicateRelationKind.EXACT.value)) or 0
    near = await db.scalar(select(func.count(SearchDuplicateRelation.id)).where(
        SearchDuplicateRelation.organization_id == actor.organization_id,
        SearchDuplicateRelation.relation_kind == DuplicateRelationKind.NEAR.value)) or 0
    last_job = await db.scalar(select(SearchIndexJob).where(
        SearchIndexJob.organization_id == actor.organization_id, SearchIndexJob.status == SearchIndexJobStatus.COMPLETED.value
    ).order_by(SearchIndexJob.finished_at.desc()).limit(1))
    payload = {"entry_count": len(entries), "chunk_count": len(entries), "exact_duplicate_pairs": int(exact), "near_duplicate_pairs": int(near),
        "by_entity": dict(by_entity), "last_completed_job_at": last_job.finished_at.isoformat() if last_job and last_job.finished_at else None}
    payload["snapshot_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


async def list_duplicates(db: AsyncSession, actor: ActorContext, *, limit: int = 100) -> list[dict]:
    relations = (await db.scalars(select(SearchDuplicateRelation).where(
        SearchDuplicateRelation.organization_id == actor.organization_id).order_by(SearchDuplicateRelation.similarity.desc()).limit(limit))).all()
    if not relations: return []
    ids = {x.left_entry_id for x in relations} | {x.right_entry_id for x in relations}
    entries = {r.id: r for r in (await db.scalars(select(SearchIndexEntry).where(SearchIndexEntry.id.in_(ids)))).all()}
    out=[]
    for rel in relations:
        a,b=entries.get(rel.left_entry_id),entries.get(rel.right_entry_id)
        if not a or not b: continue
        out.append({"id": rel.id, "kind": _v(rel.relation_kind), "similarity": rel.similarity, "hamming_distance": rel.hamming_distance,
            "shingle_jaccard": rel.shingle_jaccard, "left": {"title": a.title, "href": a.href, "matter_id": a.matter_id},
            "right": {"title": b.title, "href": b.href, "matter_id": b.matter_id}})
    return out

async def reindex_document(db: AsyncSession, document_id: UUID) -> dict:
    """Incrementally replace only one document's page chunks in the materialized index."""
    row = (await db.execute(select(Document, Matter).join(Matter, Matter.id == Document.matter_id).where(Document.id == document_id))).first()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    doc, matter = row
    if matter.organization_id is None:
        return {"document_id": document_id, "indexed_chunks": 0, "skipped": "matter has no organization"}
    pages = (await db.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number))).all()
    existing = (await db.scalars(select(SearchIndexEntry).where(
        SearchIndexEntry.organization_id == matter.organization_id,
        SearchIndexEntry.entity_type == SearchEntityType.DOCUMENT.value,
        SearchIndexEntry.entity_id == document_id,
    ))).all()
    keep: set[str] = set(); count = 0
    for page in pages:
        for chunk_no, chunk in index_document_chunks(page.text):
            entry, _ = await _put(db, organization_id=matter.organization_id, entity_type=SearchEntityType.DOCUMENT,
                entity_id=doc.id, chunk_key=f"p{page.page_number}:c{chunk_no}", title=doc.display_name or doc.filename,
                subtitle=f"Page {page.page_number}", body=chunk,
                href=f"/documents/{doc.id}?page={page.page_number}", matter_id=doc.matter_id,
                badges=[_v(doc.detected_language), _v(doc.extraction_method)],
                metadata={"page_number": page.page_number, "document_id": str(doc.id)}, rank_weight=1.0)
            keep.add(entry.source_key); count += 1
    for old in existing:
        if old.source_key not in keep:
            old.is_deleted = True
    await db.commit()
    return {"document_id": document_id, "indexed_chunks": count, "skipped": None}


async def mark_document_deleted(db: AsyncSession, document_id: UUID) -> None:
    rows = (await db.scalars(select(SearchIndexEntry).where(
        SearchIndexEntry.entity_type == SearchEntityType.DOCUMENT.value,
        SearchIndexEntry.entity_id == document_id,
        SearchIndexEntry.is_deleted.is_(False),
    ))).all()
    for row in rows:
        row.is_deleted = True
    if rows:
        await db.commit()
