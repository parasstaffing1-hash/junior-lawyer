from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document, ProcessingStatus
from app.models.document_page import DocumentPage
from app.models.evidence import (
    BundleStatus, EvidenceBundle, EvidenceBundleItem, EvidenceExhibit, EvidenceGap, EvidenceIssueLink,
    EvidenceItem, EvidenceKind, EvidenceLinkType, EvidenceReviewStatus, EvidenceStrength, EvidenceWitness,
    EvidenceWitnessLink, ExhibitStatus, GapStatus, LitigationIssue, WitnessKind, WitnessPrepQuestion,
)
from app.models.intelligence import ContradictionStatus, FactSource, FactType, MatterContradiction, MatterFact
from app.models.security import MatterAccessLevel
from app.schemas.evidence import BundleCreate, EvidenceItemUpdate, ExhibitCreate, ExhibitUpdate, IssueCreate, IssueLinkCreate, PrepQuestionCreate, WitnessCreate, WitnessLinkCreate
from app.services.documents.storage import resolve_storage_key
from app.services.evidence.classifier import classify_evidence, discover_witness_names, infer_issue_codes
from app.services.security.context import ActorContext
from app.services.security.permissions import decide_matter_access


def _norm(value: str) -> str:
    value = re.sub(r"[^\w\u0900-\u097F]+", " ", value.casefold(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


async def _access(db: AsyncSession, actor: ActorContext, matter_id: UUID, required=MatterAccessLevel.VIEW) -> None:
    decision = await decide_matter_access(db, actor, matter_id, required=required)
    if not decision.allowed:
        code = 404 if "not found" in decision.reason.casefold() else 403
        raise HTTPException(code, decision.reason)


async def _document_text(db: AsyncSession, document_id: UUID) -> str:
    rows = (await db.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number))).all()
    return "\n".join(row.text for row in rows if row.text)


async def rebuild_matter(db: AsyncSession, actor: ActorContext, matter_id: UUID) -> dict:
    await _access(db, actor, matter_id, MatterAccessLevel.WORK)
    documents = list((await db.scalars(select(Document).where(Document.matter_id == matter_id, Document.processing_status == ProcessingStatus.READY).order_by(Document.created_at))).all())
    created_items = 0
    issue_hits: dict[str, tuple[str, set[str]]] = {}
    item_text: dict[UUID, str] = {}

    for doc in documents:
        text = await _document_text(db, doc.id)
        item_text[doc.id] = text
        classification = classify_evidence(doc.filename, text)
        item = await db.scalar(select(EvidenceItem).where(EvidenceItem.matter_id == matter_id, EvidenceItem.document_id == doc.id))
        if not item:
            item = EvidenceItem(
                matter_id=matter_id, document_id=doc.id, title=doc.display_name or doc.filename,
                kind=classification.kind, confidence=classification.confidence,
                summary=(text[:500].strip() or None),
                metadata_json={"matched_terms": list(classification.matched_terms), "classifier": "deterministic-v1"},
            )
            db.add(item); await db.flush(); created_items += 1
        elif item.review_status == EvidenceReviewStatus.AUTO:
            item.kind = classification.kind; item.confidence = classification.confidence
            item.metadata_json = {**(item.metadata_json or {}), "matched_terms": list(classification.matched_terms), "classifier": "deterministic-v1"}

        for code, title, matched in infer_issue_codes(text):
            current = issue_hits.setdefault(code, (title, set()))
            current[1].update(matched)

        for name in discover_witness_names(text):
            normalized = _norm(name)
            witness = await db.scalar(select(EvidenceWitness).where(EvidenceWitness.matter_id == matter_id, EvidenceWitness.normalized_name == normalized))
            if not witness:
                witness = EvidenceWitness(matter_id=matter_id, name=name, normalized_name=normalized, kind=WitnessKind.FACT, source="deterministic")
                db.add(witness); await db.flush()
            link = await db.scalar(select(EvidenceWitnessLink).where(EvidenceWitnessLink.witness_id == witness.id, EvidenceWitnessLink.evidence_item_id == item.id))
            if not link:
                db.add(EvidenceWitnessLink(matter_id=matter_id, witness_id=witness.id, evidence_item_id=item.id, relationship="mentioned_in", confidence=0.72, rationale="Witness/deponent marker detected in document text"))

    for fact in (await db.scalars(select(MatterFact).where(MatterFact.matter_id == matter_id))).all():
        text = f"{fact.category} {fact.label} {fact.value_text}"
        for code, title, matched in infer_issue_codes(text):
            current = issue_hits.setdefault(code, (title, set()))
            current[1].update(matched)

    issues: dict[str, LitigationIssue] = {}
    for code, (title, matched) in issue_hits.items():
        issue = await db.scalar(select(LitigationIssue).where(LitigationIssue.matter_id == matter_id, LitigationIssue.code == code))
        if not issue:
            issue = LitigationIssue(matter_id=matter_id, code=code, title=title, source="deterministic", metadata_json={"matched_terms": sorted(matched)})
            db.add(issue); await db.flush()
        issues[code] = issue

    items = list((await db.scalars(select(EvidenceItem).where(EvidenceItem.matter_id == matter_id))).all())
    for item in items:
        if not item.document_id:
            continue
        text = item_text.get(item.document_id) or await _document_text(db, item.document_id)
        lower = text.casefold()
        for code, issue in issues.items():
            terms = issue.metadata_json.get("matched_terms", []) if issue.metadata_json else []
            matched = [term for term in terms if str(term).casefold() in lower]
            if not matched:
                continue
            existing = await db.scalar(select(EvidenceIssueLink).where(EvidenceIssueLink.evidence_item_id == item.id, EvidenceIssueLink.issue_id == issue.id, EvidenceIssueLink.link_type == EvidenceLinkType.SUPPORTS))
            if not existing:
                db.add(EvidenceIssueLink(matter_id=matter_id, evidence_item_id=item.id, issue_id=issue.id, link_type=EvidenceLinkType.SUPPORTS, confidence=min(0.95, 0.55 + 0.08 * len(matched)), rationale=f"Matched issue terms: {', '.join(matched[:8])}", source="deterministic"))

    await db.flush()
    await refresh_gaps(db, matter_id)
    await db.commit()
    return {"documents": len(documents), "evidence_items_created": created_items, "issues": len(issues)}


async def refresh_gaps(db: AsyncSession, matter_id: UUID) -> int:
    issues = list((await db.scalars(select(LitigationIssue).where(LitigationIssue.matter_id == matter_id))).all())
    open_keys: set[str] = set()
    for issue in issues:
        count = await db.scalar(select(func.count(EvidenceIssueLink.id)).where(EvidenceIssueLink.issue_id == issue.id, EvidenceIssueLink.link_type == EvidenceLinkType.SUPPORTS))
        if not count:
            key = f"issue:{issue.code}:no-support"
            open_keys.add(key)
            gap = await db.scalar(select(EvidenceGap).where(EvidenceGap.matter_id == matter_id, EvidenceGap.gap_key == key))
            if not gap:
                db.add(EvidenceGap(matter_id=matter_id, issue_id=issue.id, gap_key=key, title=f"No supporting evidence mapped: {issue.title}", explanation="No evidence item is currently mapped as supporting this issue.", severity="high" if issue.priority <= 2 else "medium", suggested_action="Obtain, identify, or map at least one source-backed evidence item for lawyer review."))
    contradictions = list((await db.scalars(select(MatterContradiction).where(MatterContradiction.matter_id == matter_id, MatterContradiction.status == ContradictionStatus.OPEN))).all())
    for contradiction in contradictions:
        key = f"contradiction:{contradiction.id}"
        open_keys.add(key)
        gap = await db.scalar(select(EvidenceGap).where(EvidenceGap.matter_id == matter_id, EvidenceGap.gap_key == key))
        if not gap:
            db.add(EvidenceGap(matter_id=matter_id, gap_key=key, title=f"Resolve contradiction: {contradiction.label}", explanation=contradiction.explanation, severity=contradiction.severity.value, suggested_action="Identify primary/original evidence or obtain a witness explanation before relying on this fact."))
    rows = list((await db.scalars(select(EvidenceGap).where(EvidenceGap.matter_id == matter_id, EvidenceGap.status == GapStatus.OPEN))).all())
    for row in rows:
        if (row.gap_key.startswith("issue:") or row.gap_key.startswith("contradiction:")) and row.gap_key not in open_keys:
            row.status = GapStatus.RESOLVED
    await db.flush()
    return len(open_keys)


async def dashboard(db: AsyncSession, actor: ActorContext, matter_id: UUID) -> dict:
    await _access(db, actor, matter_id)
    async def count(model, *where):
        return int(await db.scalar(select(func.count(model.id)).where(*where)) or 0)
    return {
        "evidence_items": await count(EvidenceItem, EvidenceItem.matter_id == matter_id),
        "issues": await count(LitigationIssue, LitigationIssue.matter_id == matter_id),
        "witnesses": await count(EvidenceWitness, EvidenceWitness.matter_id == matter_id),
        "open_gaps": await count(EvidenceGap, EvidenceGap.matter_id == matter_id, EvidenceGap.status == GapStatus.OPEN),
        "contradictions": await count(MatterContradiction, MatterContradiction.matter_id == matter_id, MatterContradiction.status == ContradictionStatus.OPEN),
        "proposed_exhibits": await count(EvidenceExhibit, EvidenceExhibit.matter_id == matter_id, EvidenceExhibit.status == ExhibitStatus.PROPOSED),
        "reviewed_items": await count(EvidenceItem, EvidenceItem.matter_id == matter_id, EvidenceItem.review_status == EvidenceReviewStatus.REVIEWED),
    }


async def list_items(db: AsyncSession, actor: ActorContext, matter_id: UUID):
    await _access(db, actor, matter_id)
    return list((await db.scalars(select(EvidenceItem).where(EvidenceItem.matter_id == matter_id).order_by(EvidenceItem.created_at.desc()))).all())


async def update_item(db: AsyncSession, actor: ActorContext, item_id: UUID, payload: EvidenceItemUpdate):
    row = await db.get(EvidenceItem, item_id)
    if not row: raise HTTPException(404, "Evidence item not found")
    await _access(db, actor, row.matter_id, MatterAccessLevel.WORK)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(row, key, value)
    await db.commit(); await db.refresh(row); return row


async def list_issues(db, actor, matter_id):
    await _access(db, actor, matter_id)
    return list((await db.scalars(select(LitigationIssue).where(LitigationIssue.matter_id == matter_id).order_by(LitigationIssue.priority, LitigationIssue.title))).all())


async def create_issue(db, actor, matter_id, payload: IssueCreate):
    await _access(db, actor, matter_id, MatterAccessLevel.WORK)
    row = LitigationIssue(matter_id=matter_id, source="manual", **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def link_issue(db, actor, item_id, payload: IssueLinkCreate):
    item = await db.get(EvidenceItem, item_id)
    issue = await db.get(LitigationIssue, payload.issue_id)
    if not item or not issue or item.matter_id != issue.matter_id: raise HTTPException(404, "Evidence item or issue not found")
    await _access(db, actor, item.matter_id, MatterAccessLevel.WORK)
    row = EvidenceIssueLink(matter_id=item.matter_id, evidence_item_id=item.id, issue_id=issue.id, link_type=payload.link_type, confidence=1.0, rationale=payload.rationale, source="manual")
    db.add(row); await db.commit(); await db.refresh(row); return row


async def list_links(db, actor, matter_id):
    await _access(db, actor, matter_id)
    return list((await db.scalars(select(EvidenceIssueLink).where(EvidenceIssueLink.matter_id == matter_id))).all())


async def list_witnesses(db, actor, matter_id):
    await _access(db, actor, matter_id)
    return list((await db.scalars(select(EvidenceWitness).where(EvidenceWitness.matter_id == matter_id).order_by(EvidenceWitness.name))).all())


async def create_witness(db, actor, matter_id, payload: WitnessCreate):
    await _access(db, actor, matter_id, MatterAccessLevel.WORK)
    normalized = _norm(payload.name)
    existing = await db.scalar(select(EvidenceWitness).where(EvidenceWitness.matter_id == matter_id, EvidenceWitness.normalized_name == normalized))
    if existing: return existing
    row = EvidenceWitness(matter_id=matter_id, normalized_name=normalized, source="manual", **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def link_witness(db, actor, witness_id, payload: WitnessLinkCreate):
    witness = await db.get(EvidenceWitness, witness_id); item = await db.get(EvidenceItem, payload.evidence_item_id)
    if not witness or not item or witness.matter_id != item.matter_id: raise HTTPException(404, "Witness or evidence item not found")
    await _access(db, actor, witness.matter_id, MatterAccessLevel.WORK)
    row = EvidenceWitnessLink(matter_id=witness.matter_id, witness_id=witness.id, evidence_item_id=item.id, relationship=payload.relationship, confidence=1.0, rationale=payload.rationale)
    db.add(row); await db.commit(); await db.refresh(row); return row


async def list_witness_links(db, actor, matter_id):
    await _access(db, actor, matter_id)
    return list((await db.scalars(select(EvidenceWitnessLink).where(EvidenceWitnessLink.matter_id == matter_id))).all())


async def list_gaps(db, actor, matter_id):
    await _access(db, actor, matter_id)
    return list((await db.scalars(select(EvidenceGap).where(EvidenceGap.matter_id == matter_id).order_by(EvidenceGap.status, EvidenceGap.severity.desc(), EvidenceGap.created_at.desc()))).all())


async def update_gap(db, actor, gap_id, status):
    row=await db.get(EvidenceGap,gap_id)
    if not row: raise HTTPException(404,"Evidence gap not found")
    await _access(db,actor,row.matter_id,MatterAccessLevel.WORK); row.status=status; await db.commit(); await db.refresh(row); return row


async def list_exhibits(db, actor, matter_id):
    await _access(db, actor, matter_id)
    return list((await db.scalars(select(EvidenceExhibit).where(EvidenceExhibit.matter_id == matter_id).order_by(EvidenceExhibit.label))).all())


async def create_exhibit(db, actor, matter_id, payload: ExhibitCreate):
    await _access(db, actor, matter_id, MatterAccessLevel.WORK)
    item=await db.get(EvidenceItem,payload.evidence_item_id)
    if not item or item.matter_id!=matter_id: raise HTTPException(404,"Evidence item not found")
    row=EvidenceExhibit(matter_id=matter_id,status=ExhibitStatus.PROPOSED,**payload.model_dump()); db.add(row); await db.commit(); await db.refresh(row); return row


async def update_exhibit(db, actor, exhibit_id, payload: ExhibitUpdate):
    row=await db.get(EvidenceExhibit,exhibit_id)
    if not row: raise HTTPException(404,"Exhibit not found")
    await _access(db,actor,row.matter_id,MatterAccessLevel.WORK)
    for k,v in payload.model_dump(exclude_unset=True).items(): setattr(row,k,v)
    await db.commit(); await db.refresh(row); return row


async def graph(db: AsyncSession, actor: ActorContext, matter_id: UUID) -> dict:
    await _access(db, actor, matter_id)
    issues=await list_issues(db,actor,matter_id); items=await list_items(db,actor,matter_id); witnesses=await list_witnesses(db,actor,matter_id)
    issue_links=await list_links(db,actor,matter_id); witness_links=await list_witness_links(db,actor,matter_id)
    nodes=[]; edges=[]
    for i in issues: nodes.append({"id":f"issue:{i.id}","type":"issue","label":i.title,"metadata":{"priority":i.priority}})
    for e in items: nodes.append({"id":f"evidence:{e.id}","type":"evidence","label":e.title,"metadata":{"kind":e.kind.value,"strength":e.strength.value}})
    for w in witnesses: nodes.append({"id":f"witness:{w.id}","type":"witness","label":w.name,"metadata":{"kind":w.kind.value,"side":w.side}})
    for l in issue_links: edges.append({"source":f"evidence:{l.evidence_item_id}","target":f"issue:{l.issue_id}","type":l.link_type.value,"metadata":{"confidence":l.confidence}})
    for l in witness_links: edges.append({"source":f"witness:{l.witness_id}","target":f"evidence:{l.evidence_item_id}","type":l.relationship,"metadata":{"confidence":l.confidence}})
    money_facts=list((await db.scalars(select(MatterFact).where(MatterFact.matter_id==matter_id, MatterFact.fact_type==FactType.MONEY))).all())
    item_by_document={item.document_id:item for item in items if item.document_id}
    for fact in money_facts:
        node_id=f"transaction:{fact.id}"
        nodes.append({"id":node_id,"type":"transaction","label":f"{fact.label}: {fact.value_text}","metadata":{"category":fact.category,"confidence":fact.confidence}})
        sources=list((await db.scalars(select(FactSource).where(FactSource.fact_id==fact.id))).all())
        for source in sources:
            item=item_by_document.get(source.document_id)
            if item:
                edges.append({"source":node_id,"target":f"evidence:{item.id}","type":"supported_by","metadata":{"page_number":source.page_number,"confidence":source.confidence}})
    return {"nodes":nodes,"edges":edges}


async def add_prep_question(db, actor, witness_id, payload: PrepQuestionCreate):
    witness=await db.get(EvidenceWitness,witness_id)
    if not witness: raise HTTPException(404,"Witness not found")
    await _access(db,actor,witness.matter_id,MatterAccessLevel.WORK)
    row=WitnessPrepQuestion(matter_id=witness.matter_id,witness_id=witness.id,source="manual",**payload.model_dump()); db.add(row); await db.commit(); await db.refresh(row); return row


async def generate_prep_questions(db, actor, witness_id):
    witness=await db.get(EvidenceWitness,witness_id)
    if not witness: raise HTTPException(404,"Witness not found")
    await _access(db,actor,witness.matter_id,MatterAccessLevel.WORK)
    links=list((await db.scalars(select(EvidenceWitnessLink).where(EvidenceWitnessLink.witness_id==witness.id))).all())
    created=[]
    base=[
        ("foundation", f"Please state your full name, role, and your connection with the matter involving {witness.name}."),
        ("foundation", "How do you have personal knowledge of the events you are describing?"),
        ("credibility", "Which records or contemporaneous documents can independently verify your recollection?"),
    ]
    for qtype,q in base:
        row=WitnessPrepQuestion(matter_id=witness.matter_id,witness_id=witness.id,question=q,question_type=qtype,purpose="Deterministic witness-preparation prompt; lawyer must adapt before use",source="deterministic")
        db.add(row); created.append(row)
    for link in links[:20]:
        item=await db.get(EvidenceItem,link.evidence_item_id)
        if item:
            row=WitnessPrepQuestion(matter_id=witness.matter_id,witness_id=witness.id,evidence_item_id=item.id,question=f"Please explain what you know about the document '{item.title}' and how you can identify or authenticate it.",question_type="document_foundation",purpose="Establish witness connection to mapped evidence",source="deterministic")
            db.add(row); created.append(row)
    await db.commit(); return created


async def list_prep_questions(db, actor, witness_id):
    witness=await db.get(EvidenceWitness,witness_id)
    if not witness: raise HTTPException(404,"Witness not found")
    await _access(db,actor,witness.matter_id)
    return list((await db.scalars(select(WitnessPrepQuestion).where(WitnessPrepQuestion.witness_id==witness_id).order_by(WitnessPrepQuestion.created_at))).all())


async def create_bundle(db: AsyncSession, actor: ActorContext, matter_id: UUID, payload: BundleCreate):
    decision=await decide_matter_access(db,actor,matter_id,required=MatterAccessLevel.WORK)
    if not decision.allowed: raise HTTPException(403,decision.reason)
    if decision.export_allowed is False: raise HTTPException(403,"Exports are disabled for this matter")
    item_ids=list(payload.evidence_item_ids)
    if not item_ids and payload.issue_ids:
        item_ids=list((await db.scalars(select(EvidenceIssueLink.evidence_item_id).where(EvidenceIssueLink.issue_id.in_(payload.issue_ids)))).all())
    if not item_ids:
        item_ids=list((await db.scalars(select(EvidenceItem.id).where(EvidenceItem.matter_id==matter_id))).all())
    seen=[]
    for item_id in item_ids:
        if item_id not in seen: seen.append(item_id)
    items=list((await db.scalars(select(EvidenceItem).where(EvidenceItem.id.in_(seen),EvidenceItem.matter_id==matter_id))).all()) if seen else []
    by_id={i.id:i for i in items}
    ordered=[by_id[i] for i in seen if i in by_id]
    bundle=EvidenceBundle(matter_id=matter_id,title=payload.title,bundle_type=payload.bundle_type,status=BundleStatus.DRAFT,created_by_user_id=actor.user_id,description=payload.description,metadata_json={"item_count":len(ordered),"issue_ids":[str(i) for i in payload.issue_ids]})
    db.add(bundle); await db.flush()
    for idx,item in enumerate(ordered,1): db.add(EvidenceBundleItem(bundle_id=bundle.id,evidence_item_id=item.id,position=idx,section_label=item.kind.value.replace("_"," ").title(),included_reason="Selected for litigation bundle"))
    await db.flush()
    path,digest=await _write_bundle_zip(db,bundle,ordered)
    bundle.storage_key=path; bundle.sha256=digest
    await db.commit(); await db.refresh(bundle); return bundle


async def _write_bundle_zip(db: AsyncSession, bundle: EvidenceBundle, items: list[EvidenceItem]) -> tuple[str,str]:
    relative=Path("bundles")/str(bundle.matter_id)/f"{bundle.id}.zip"
    target=(settings.storage_root/relative).resolve(); target.parent.mkdir(parents=True,exist_ok=True)
    manifest=io.StringIO(); writer=csv.writer(manifest); writer.writerow(["No.","Title","Kind","SHA-256","Original file"])
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        index_lines=[f"# {bundle.title}","",("FINAL LITIGATION BUNDLE" if bundle.status == BundleStatus.FINAL else "DRAFT LITIGATION BUNDLE — LAWYER REVIEW REQUIRED"),"",]
        for idx,item in enumerate(items,1):
            doc=await db.get(Document,item.document_id) if item.document_id else None
            filename=doc.filename if doc else ""
            writer.writerow([idx,item.title,item.kind.value,doc.sha256 if doc else "",filename])
            index_lines.append(f"{idx}. {item.title} — {item.kind.value}")
            if doc and doc.storage_key:
                source=resolve_storage_key(doc.storage_key)
                if source.exists(): archive.write(source,arcname=f"documents/{idx:03d}-{Path(filename).name}")
        archive.writestr("INDEX.md","\n".join(index_lines))
        archive.writestr("manifest.csv",manifest.getvalue())
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    return relative.as_posix(),digest


async def finalize_bundle(db: AsyncSession, actor: ActorContext, bundle_id: UUID):
    bundle=await db.get(EvidenceBundle,bundle_id)
    if not bundle: raise HTTPException(404,"Bundle not found")
    decision=await decide_matter_access(db,actor,bundle.matter_id,required=MatterAccessLevel.WORK)
    if not decision.allowed: raise HTTPException(403,decision.reason)
    if decision.export_allowed is False: raise HTTPException(403,"Exports are disabled for this matter")
    ids=list((await db.scalars(select(EvidenceBundleItem.evidence_item_id).where(EvidenceBundleItem.bundle_id==bundle.id).order_by(EvidenceBundleItem.position))).all())
    items=list((await db.scalars(select(EvidenceItem).where(EvidenceItem.id.in_(ids)))).all()) if ids else []
    by_id={i.id:i for i in items}; ordered=[by_id[i] for i in ids if i in by_id]
    unreviewed=[i.title for i in ordered if i.review_status != EvidenceReviewStatus.REVIEWED]
    if unreviewed:
        raise HTTPException(409,{"message":"Every bundled evidence item must be lawyer-reviewed before finalization","unreviewed":unreviewed[:20]})
    bundle.status=BundleStatus.FINAL
    path,digest=await _write_bundle_zip(db,bundle,ordered); bundle.storage_key=path; bundle.sha256=digest
    bundle.metadata_json={**(bundle.metadata_json or {}),"finalized_by_user_id":str(actor.user_id)}
    await db.commit(); await db.refresh(bundle); return bundle


async def list_bundles(db, actor, matter_id):
    await _access(db,actor,matter_id)
    return list((await db.scalars(select(EvidenceBundle).where(EvidenceBundle.matter_id==matter_id).order_by(EvidenceBundle.created_at.desc()))).all())


async def bundle_file(db, actor, bundle_id):
    row=await db.get(EvidenceBundle,bundle_id)
    if not row or not row.storage_key: raise HTTPException(404,"Bundle not found")
    decision=await decide_matter_access(db,actor,row.matter_id,required=MatterAccessLevel.VIEW)
    if not decision.allowed: raise HTTPException(403,decision.reason)
    if decision.export_allowed is False: raise HTTPException(403,"Exports are disabled for this matter")
    path=(settings.storage_root/row.storage_key).resolve()
    if not path.exists(): raise HTTPException(404,"Bundle file missing")
    return row,path
