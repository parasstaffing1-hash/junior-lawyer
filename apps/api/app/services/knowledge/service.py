from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract, ContractClause
from app.models.drafting import LegalDraft, LegalDraftSection
from app.models.knowledge import (
    KnowledgeAnnotation, KnowledgeAsset, KnowledgeAssetSource, KnowledgeAssetStatus, KnowledgeAssetTag,
    KnowledgeAssetVersion, KnowledgeCollection, KnowledgeCollectionStatus, KnowledgeLanguage, KnowledgeSourceType,
    KnowledgeTag, MatterPlaybook, MatterPlaybookItem, MatterPlaybookStatus, ResearchCollection,
    ResearchCollectionItem, ResearchCollectionStatus, SanitizationStatus,
)
from app.models.legal_corpus import Judgment, JudgmentParagraph
from app.models.security import AuditOutcome, MatterAccessLevel, OrganizationRole
from app.schemas.knowledge import (
    AnnotationCreate, KnowledgeAssetCreate, KnowledgeAssetUpdate, KnowledgeCollectionCreate,
    MatterPlaybookCreate, MatterPlaybookItemCreate, PromoteContractClauseRequest, PromoteDraftSectionRequest,
    ResearchCollectionCreate, ResearchCollectionItemCreate,
)
from app.services.knowledge.ranking import build_search_text, content_hash, rank_knowledge
from app.services.language.normalizer import normalize_legal_text
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext
from app.services.security.permissions import decide_matter_access


REVIEWER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _reviewer(actor: ActorContext) -> None:
    if actor.role not in REVIEWER_ROLES:
        raise HTTPException(403, "Partner, admin, or owner review is required")


def _tag_key(value: str) -> str:
    return " ".join(normalize_legal_text(value).casefold().split())[:160]


def _validate_language_content(language: KnowledgeLanguage, body_en: str | None, body_hi: str | None) -> None:
    if language == KnowledgeLanguage.ENGLISH and not (body_en or "").strip():
        raise HTTPException(422, "English body is required for an English knowledge asset")
    if language == KnowledgeLanguage.HINDI and not (body_hi or "").strip():
        raise HTTPException(422, "Hindi body is required for a Hindi knowledge asset")
    if language == KnowledgeLanguage.BILINGUAL and (not (body_en or "").strip() or not (body_hi or "").strip()):
        raise HTTPException(422, "Both English and Hindi bodies are required for a bilingual knowledge asset")


async def _matter_access(db: AsyncSession, actor: ActorContext, matter_id: UUID, required: MatterAccessLevel = MatterAccessLevel.VIEW) -> None:
    decision = await decide_matter_access(db, actor, matter_id, required=required)
    if not decision.allowed:
        raise HTTPException(403, decision.reason)


async def _asset_tags(db: AsyncSession, asset_ids: list[UUID]) -> dict[UUID, list[str]]:
    if not asset_ids:
        return {}
    rows = (
        await db.execute(
            select(KnowledgeAssetTag.asset_id, KnowledgeTag.display_name)
            .join(KnowledgeTag, KnowledgeTag.id == KnowledgeAssetTag.tag_id)
            .where(KnowledgeAssetTag.asset_id.in_(asset_ids))
        )
    ).all()
    result: dict[UUID, list[str]] = {}
    for asset_id, name in rows:
        result.setdefault(asset_id, []).append(name)
    return result


async def _get_asset(db: AsyncSession, actor: ActorContext, asset_id: UUID, *, work: bool = False) -> KnowledgeAsset:
    asset = await db.get(KnowledgeAsset, asset_id)
    if not asset or asset.organization_id != actor.organization_id:
        raise HTTPException(404, "Knowledge asset not found")
    if asset.status == KnowledgeAssetStatus.APPROVED:
        return asset
    if asset.source_matter_id:
        await _matter_access(db, actor, asset.source_matter_id, MatterAccessLevel.WORK if work else MatterAccessLevel.VIEW)
        return asset
    if asset.created_by_membership_id == actor.membership_id or actor.role in REVIEWER_ROLES:
        return asset
    raise HTTPException(403, "This draft knowledge asset is not visible to you")


async def create_collection(db: AsyncSession, actor: ActorContext, payload: KnowledgeCollectionCreate) -> KnowledgeCollection:
    row = KnowledgeCollection(
        organization_id=actor.organization_id,
        created_by_membership_id=actor.membership_id,
        status=KnowledgeCollectionStatus.ACTIVE,
        **payload.model_dump(),
    )
    db.add(row)
    await db.commit(); await db.refresh(row)
    return row


async def list_collections(db: AsyncSession, actor: ActorContext) -> list[KnowledgeCollection]:
    return list((await db.scalars(select(KnowledgeCollection).where(KnowledgeCollection.organization_id == actor.organization_id, KnowledgeCollection.status == KnowledgeCollectionStatus.ACTIVE).order_by(KnowledgeCollection.name))).all())


async def _upsert_tags(db: AsyncSession, actor: ActorContext, asset: KnowledgeAsset, tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for raw in tags:
        display = " ".join(raw.split()).strip()
        key = _tag_key(display)
        if not key or key in {_tag_key(v) for v in cleaned}:
            continue
        tag = await db.scalar(select(KnowledgeTag).where(KnowledgeTag.organization_id == actor.organization_id, KnowledgeTag.normalized_name == key))
        if not tag:
            tag = KnowledgeTag(organization_id=actor.organization_id, normalized_name=key, display_name=display, language=KnowledgeLanguage.HINDI if any("\u0900" <= c <= "\u097f" for c in display) else KnowledgeLanguage.ENGLISH)
            db.add(tag); await db.flush()
        existing = await db.scalar(select(KnowledgeAssetTag).where(KnowledgeAssetTag.asset_id == asset.id, KnowledgeAssetTag.tag_id == tag.id))
        if not existing:
            db.add(KnowledgeAssetTag(asset_id=asset.id, tag_id=tag.id))
        cleaned.append(display)
    return cleaned


async def create_asset(db: AsyncSession, actor: ActorContext, payload: KnowledgeAssetCreate) -> KnowledgeAsset:
    _validate_language_content(payload.language, payload.body_en, payload.body_hi)
    if payload.source_matter_id:
        await _matter_access(db, actor, payload.source_matter_id, MatterAccessLevel.WORK)
    if payload.collection_id:
        collection = await db.get(KnowledgeCollection, payload.collection_id)
        if not collection or collection.organization_id != actor.organization_id:
            raise HTTPException(404, "Knowledge collection not found")
    for source in payload.sources:
        if source.source_matter_id:
            await _matter_access(db, actor, source.source_matter_id, MatterAccessLevel.VIEW)
    h = content_hash(title=payload.title, body_en=payload.body_en, body_hi=payload.body_hi, summary=payload.summary)
    row = KnowledgeAsset(
        organization_id=actor.organization_id,
        collection_id=payload.collection_id,
        source_matter_id=payload.source_matter_id,
        created_by_membership_id=actor.membership_id,
        title=payload.title,
        kind=payload.kind,
        language=payload.language,
        status=KnowledgeAssetStatus.DRAFT,
        sanitization_status=SanitizationStatus.NOT_REVIEWED if payload.source_matter_id else SanitizationStatus.NOT_REQUIRED,
        body_en=payload.body_en,
        body_hi=payload.body_hi,
        summary=payload.summary,
        jurisdiction=payload.jurisdiction,
        practice_area=payload.practice_area,
        matter_type=payload.matter_type,
        outcome_label=payload.outcome_label,
        quality_score=0.5,
        search_text=build_search_text(title=payload.title, body_en=payload.body_en, body_hi=payload.body_hi, summary=payload.summary, tags=payload.tags, practice_area=payload.practice_area, matter_type=payload.matter_type),
        content_hash=h,
        metadata_json=payload.metadata_json,
    )
    db.add(row); await db.flush()
    for source in payload.sources:
        db.add(KnowledgeAssetSource(asset_id=row.id, **source.model_dump()))
    await _upsert_tags(db, actor, row, payload.tags)
    db.add(KnowledgeAssetVersion(asset_id=row.id, version_number=1, label="Created", title=row.title, body_en=row.body_en, body_hi=row.body_hi, summary=row.summary, content_hash=row.content_hash, created_by_membership_id=actor.membership_id))
    await append_audit_event(db, organization_id=actor.organization_id, action="knowledge.asset.create", resource_type="knowledge_asset", resource_id=str(row.id), outcome=AuditOutcome.SUCCESS, actor=actor, metadata={"kind": row.kind.value, "source_matter_id": str(row.source_matter_id) if row.source_matter_id else None})
    await db.commit(); await db.refresh(row)
    return row


async def update_asset(db: AsyncSession, actor: ActorContext, asset_id: UUID, payload: KnowledgeAssetUpdate) -> KnowledgeAsset:
    asset = await _get_asset(db, actor, asset_id, work=True)
    if "collection_id" in payload.model_fields_set and payload.collection_id is not None:
        collection = await db.get(KnowledgeCollection, payload.collection_id)
        if not collection or collection.organization_id != actor.organization_id:
            raise HTTPException(404, "Knowledge collection not found")
    before_hash = asset.content_hash
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    _validate_language_content(asset.language, asset.body_en, asset.body_hi)
    tags = (await _asset_tags(db, [asset.id])).get(asset.id, [])
    asset.search_text = build_search_text(title=asset.title, body_en=asset.body_en, body_hi=asset.body_hi, summary=asset.summary, tags=tags, practice_area=asset.practice_area, matter_type=asset.matter_type)
    asset.content_hash = content_hash(title=asset.title, body_en=asset.body_en, body_hi=asset.body_hi, summary=asset.summary)
    if asset.content_hash != before_hash:
        current_max = int(await db.scalar(select(func.max(KnowledgeAssetVersion.version_number)).where(KnowledgeAssetVersion.asset_id == asset.id)) or 0)
        db.add(KnowledgeAssetVersion(asset_id=asset.id, version_number=current_max + 1, label="Edited", title=asset.title, body_en=asset.body_en, body_hi=asset.body_hi, summary=asset.summary, content_hash=asset.content_hash, created_by_membership_id=actor.membership_id))
        asset.status = KnowledgeAssetStatus.IN_REVIEW if asset.status == KnowledgeAssetStatus.APPROVED else asset.status
        if asset.source_matter_id:
            asset.sanitization_status = SanitizationStatus.NOT_REVIEWED
        asset.approved_by_membership_id = None
        asset.approved_at = None
    await db.commit(); await db.refresh(asset); return asset


async def submit_for_review(db: AsyncSession, actor: ActorContext, asset_id: UUID) -> KnowledgeAsset:
    asset = await _get_asset(db, actor, asset_id, work=True)
    if asset.status == KnowledgeAssetStatus.RETIRED:
        raise HTTPException(409, "Retired knowledge cannot be submitted")
    asset.status = KnowledgeAssetStatus.IN_REVIEW
    await db.commit(); await db.refresh(asset); return asset


async def approve_asset(db: AsyncSession, actor: ActorContext, asset_id: UUID, *, sanitization_status: SanitizationStatus, review_note: str | None) -> KnowledgeAsset:
    _reviewer(actor)
    asset = await _get_asset(db, actor, asset_id, work=True)
    if asset.source_matter_id:
        await _matter_access(db, actor, asset.source_matter_id, MatterAccessLevel.VIEW)
        if sanitization_status != SanitizationStatus.REVIEWED:
            raise HTTPException(409, "Matter-derived knowledge must be explicitly sanitized/reviewed before firm-wide approval")
    _validate_language_content(asset.language, asset.body_en, asset.body_hi)
    sources = list((await db.scalars(select(KnowledgeAssetSource).where(KnowledgeAssetSource.asset_id == asset.id))).all())
    if asset.source_matter_id and not any(source.verified for source in sources):
        raise HTTPException(409, "At least one source must be verified before approving matter-derived knowledge")
    asset.sanitization_status = sanitization_status
    asset.status = KnowledgeAssetStatus.APPROVED
    asset.approved_by_membership_id = actor.membership_id
    asset.approved_at = _now()
    meta = dict(asset.metadata_json or {})
    if review_note:
        meta["approval_note"] = review_note
    asset.metadata_json = meta
    await append_audit_event(db, organization_id=actor.organization_id, action="knowledge.asset.approve", resource_type="knowledge_asset", resource_id=str(asset.id), outcome=AuditOutcome.SUCCESS, actor=actor, metadata={"sanitization_status": sanitization_status.value})
    await db.commit(); await db.refresh(asset); return asset


async def retire_asset(db: AsyncSession, actor: ActorContext, asset_id: UUID) -> KnowledgeAsset:
    _reviewer(actor)
    asset = await _get_asset(db, actor, asset_id, work=True)
    asset.status = KnowledgeAssetStatus.RETIRED
    await db.commit(); await db.refresh(asset); return asset


async def list_assets(db: AsyncSession, actor: ActorContext, *, status: KnowledgeAssetStatus | None = None, kind=None, limit: int = 200) -> list[KnowledgeAsset]:
    stmt = select(KnowledgeAsset).where(KnowledgeAsset.organization_id == actor.organization_id)
    if status:
        stmt = stmt.where(KnowledgeAsset.status == status)
    if kind:
        stmt = stmt.where(KnowledgeAsset.kind == kind)
    rows = list((await db.scalars(stmt.order_by(KnowledgeAsset.updated_at.desc()).limit(limit))).all())
    visible: list[KnowledgeAsset] = []
    for row in rows:
        if row.status == KnowledgeAssetStatus.APPROVED:
            visible.append(row); continue
        try:
            await _get_asset(db, actor, row.id)
            visible.append(row)
        except HTTPException:
            pass
    return visible


async def asset_detail(db: AsyncSession, actor: ActorContext, asset_id: UUID) -> dict:
    asset = await _get_asset(db, actor, asset_id)
    sources = list((await db.scalars(select(KnowledgeAssetSource).where(KnowledgeAssetSource.asset_id == asset.id).order_by(KnowledgeAssetSource.created_at))).all())
    restricted = False
    safe_sources: list[KnowledgeAssetSource] = []
    for source in sources:
        if source.source_matter_id:
            decision = await decide_matter_access(db, actor, source.source_matter_id)
            if not decision.allowed:
                restricted = True
                continue
        safe_sources.append(source)
    tags = (await _asset_tags(db, [asset.id])).get(asset.id, [])
    return {"asset": asset, "sources": safe_sources, "tags": tags, "source_access_restricted": restricted}


async def search_assets(db: AsyncSession, actor: ActorContext, query: str, *, kind=None, practice_area: str | None = None, limit: int = 25) -> dict:
    stmt = select(KnowledgeAsset).where(KnowledgeAsset.organization_id == actor.organization_id, KnowledgeAsset.status == KnowledgeAssetStatus.APPROVED)
    if kind:
        stmt = stmt.where(KnowledgeAsset.kind == kind)
    if practice_area:
        stmt = stmt.where(func.lower(KnowledgeAsset.practice_area) == practice_area.casefold())
    assets = list((await db.scalars(stmt.limit(1000))).all())
    tag_map = await _asset_tags(db, [a.id for a in assets])
    docs = [build_search_text(title=a.title, body_en=a.body_en, body_hi=a.body_hi, summary=a.summary, tags=tag_map.get(a.id, []), practice_area=a.practice_area, matter_type=a.matter_type) for a in assets]
    normalized, ranked = rank_knowledge(query, docs, [a.quality_score for a in assets], limit=limit)
    results = []
    for item in ranked:
        asset = assets[item.index]
        asset.usage_count += 1
        results.append({"asset": asset, "score": item.final_score, "lexical_score": item.lexical_score, "quality_score": item.quality_score, "snippet": item.snippet, "tags": tag_map.get(asset.id, [])})
    if results:
        await db.commit()
    return {"query": query, "normalized_query": normalized, "results": results}


async def versions(db: AsyncSession, actor: ActorContext, asset_id: UUID) -> list[KnowledgeAssetVersion]:
    await _get_asset(db, actor, asset_id)
    return list((await db.scalars(select(KnowledgeAssetVersion).where(KnowledgeAssetVersion.asset_id == asset_id).order_by(KnowledgeAssetVersion.version_number.desc()))).all())


async def add_annotation(db: AsyncSession, actor: ActorContext, asset_id: UUID, payload: AnnotationCreate) -> KnowledgeAnnotation:
    await _get_asset(db, actor, asset_id)
    row = KnowledgeAnnotation(asset_id=asset_id, membership_id=actor.membership_id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def annotations(db: AsyncSession, actor: ActorContext, asset_id: UUID) -> list[KnowledgeAnnotation]:
    await _get_asset(db, actor, asset_id)
    return list((await db.scalars(select(KnowledgeAnnotation).where(KnowledgeAnnotation.asset_id == asset_id).order_by(KnowledgeAnnotation.created_at.desc()))).all())


async def promote_draft_section(db: AsyncSession, actor: ActorContext, payload: PromoteDraftSectionRequest) -> KnowledgeAsset:
    section = await db.get(LegalDraftSection, payload.section_id)
    if not section:
        raise HTTPException(404, "Draft section not found")
    draft = await db.get(LegalDraft, section.draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    await _matter_access(db, actor, draft.matter_id, MatterAccessLevel.WORK)
    language = KnowledgeLanguage.BILINGUAL if (section.body_en and section.body_hi) else (KnowledgeLanguage.HINDI if section.body_hi and not section.body_en else KnowledgeLanguage.ENGLISH)
    title = payload.title or section.title_en or section.title_hi or section.section_key
    create = KnowledgeAssetCreate(collection_id=payload.collection_id, source_matter_id=draft.matter_id, title=title, kind=payload.kind, language=language, body_en=section.body_en or None, body_hi=section.body_hi or None, summary=f"Promoted from approved/reviewed legal drafting work product: {draft.title}", jurisdiction="India", practice_area=payload.practice_area, matter_type=payload.matter_type, tags=payload.tags, sources=[{"source_type": KnowledgeSourceType.DRAFT_SECTION, "source_id": section.id, "source_matter_id": draft.matter_id, "label": draft.title, "locator": section.section_key, "excerpt": (section.body_en or section.body_hi or "")[:1000], "verified": bool(section.reviewed)}])
    return await create_asset(db, actor, create)


async def promote_contract_clause(db: AsyncSession, actor: ActorContext, payload: PromoteContractClauseRequest) -> KnowledgeAsset:
    clause = await db.get(ContractClause, payload.clause_id)
    if not clause:
        raise HTTPException(404, "Contract clause not found")
    contract = await db.get(Contract, clause.contract_id)
    if not contract or contract.organization_id not in {None, actor.organization_id}:
        raise HTTPException(404, "Contract not found")
    if contract.matter_id:
        await _matter_access(db, actor, contract.matter_id, MatterAccessLevel.WORK)
    language = KnowledgeLanguage.BILINGUAL if clause.body_hi else KnowledgeLanguage.ENGLISH
    create = KnowledgeAssetCreate(collection_id=payload.collection_id, source_matter_id=contract.matter_id, title=payload.title or clause.title_en, kind="contract_clause", language=language, body_en=clause.body_en, body_hi=clause.body_hi, summary=f"Promoted from contract: {contract.title}", jurisdiction=contract.jurisdiction, practice_area=payload.practice_area, matter_type=payload.matter_type or contract.contract_type.value, tags=payload.tags, sources=[{"source_type": KnowledgeSourceType.CONTRACT_CLAUSE, "source_id": clause.id, "source_matter_id": contract.matter_id, "label": contract.title, "locator": clause.clause_code, "excerpt": clause.body_en[:1000], "verified": bool(contract.approved_at)}])
    return await create_asset(db, actor, create)


async def create_playbook(db: AsyncSession, actor: ActorContext, payload: MatterPlaybookCreate) -> MatterPlaybook:
    row = MatterPlaybook(organization_id=actor.organization_id, created_by_membership_id=actor.membership_id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def list_playbooks(db: AsyncSession, actor: ActorContext) -> list[MatterPlaybook]:
    return list((await db.scalars(select(MatterPlaybook).where(MatterPlaybook.organization_id == actor.organization_id).order_by(MatterPlaybook.updated_at.desc()))).all())


async def add_playbook_item(db: AsyncSession, actor: ActorContext, playbook_id: UUID, payload: MatterPlaybookItemCreate) -> MatterPlaybookItem:
    playbook = await db.get(MatterPlaybook, playbook_id)
    if not playbook or playbook.organization_id != actor.organization_id:
        raise HTTPException(404, "Playbook not found")
    if payload.asset_id:
        asset = await _get_asset(db, actor, payload.asset_id)
        if asset.status != KnowledgeAssetStatus.APPROVED:
            raise HTTPException(409, "Only approved knowledge assets may be embedded in matter playbooks")
    row = MatterPlaybookItem(playbook_id=playbook_id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def playbook_items(db: AsyncSession, actor: ActorContext, playbook_id: UUID) -> list[MatterPlaybookItem]:
    playbook = await db.get(MatterPlaybook, playbook_id)
    if not playbook or playbook.organization_id != actor.organization_id:
        raise HTTPException(404, "Playbook not found")
    return list((await db.scalars(select(MatterPlaybookItem).where(MatterPlaybookItem.playbook_id == playbook_id).order_by(MatterPlaybookItem.position))).all())


async def approve_playbook(db: AsyncSession, actor: ActorContext, playbook_id: UUID) -> MatterPlaybook:
    _reviewer(actor)
    playbook = await db.get(MatterPlaybook, playbook_id)
    if not playbook or playbook.organization_id != actor.organization_id:
        raise HTTPException(404, "Playbook not found")
    items = await playbook_items(db, actor, playbook_id)
    if not items:
        raise HTTPException(409, "Playbook must contain at least one item")
    linked = [item.asset_id for item in items if item.asset_id]
    if linked:
        assets = list((await db.scalars(select(KnowledgeAsset).where(KnowledgeAsset.id.in_(linked)))).all())
        if len(assets) != len(set(linked)) or any(a.status != KnowledgeAssetStatus.APPROVED for a in assets):
            raise HTTPException(409, "All linked knowledge assets must be approved")
    playbook.status = MatterPlaybookStatus.APPROVED; playbook.approved_by_membership_id = actor.membership_id; playbook.approved_at = _now()
    await db.commit(); await db.refresh(playbook); return playbook


async def create_research_collection(db: AsyncSession, actor: ActorContext, payload: ResearchCollectionCreate) -> ResearchCollection:
    row = ResearchCollection(organization_id=actor.organization_id, created_by_membership_id=actor.membership_id, **payload.model_dump())
    db.add(row); await db.commit(); await db.refresh(row); return row


async def list_research_collections(db: AsyncSession, actor: ActorContext) -> list[ResearchCollection]:
    return list((await db.scalars(select(ResearchCollection).where(ResearchCollection.organization_id == actor.organization_id).order_by(ResearchCollection.updated_at.desc()))).all())


async def add_research_item(db: AsyncSession, actor: ActorContext, collection_id: UUID, payload: ResearchCollectionItemCreate) -> ResearchCollectionItem:
    collection = await db.get(ResearchCollection, collection_id)
    if not collection or collection.organization_id != actor.organization_id:
        raise HTTPException(404, "Research collection not found")
    judgment = await db.get(Judgment, payload.judgment_id)
    if not judgment:
        raise HTTPException(404, "Judgment not found")
    if payload.paragraph_id:
        paragraph = await db.get(JudgmentParagraph, payload.paragraph_id)
        if not paragraph or paragraph.judgment_id != judgment.id:
            raise HTTPException(422, "Paragraph does not belong to the selected judgment")
    row = ResearchCollectionItem(collection_id=collection_id, **payload.model_dump(), metadata_json={})
    db.add(row); await db.commit(); await db.refresh(row); return row


async def research_items(db: AsyncSession, actor: ActorContext, collection_id: UUID) -> list[ResearchCollectionItem]:
    collection = await db.get(ResearchCollection, collection_id)
    if not collection or collection.organization_id != actor.organization_id:
        raise HTTPException(404, "Research collection not found")
    return list((await db.scalars(select(ResearchCollectionItem).where(ResearchCollectionItem.collection_id == collection_id).order_by(ResearchCollectionItem.position))).all())


async def approve_research_collection(db: AsyncSession, actor: ActorContext, collection_id: UUID) -> ResearchCollection:
    _reviewer(actor)
    collection = await db.get(ResearchCollection, collection_id)
    if not collection or collection.organization_id != actor.organization_id:
        raise HTTPException(404, "Research collection not found")
    items = await research_items(db, actor, collection_id)
    if not items or any(not item.verified for item in items):
        raise HTTPException(409, "Every authority in an approved collection must be verified")
    collection.status = ResearchCollectionStatus.APPROVED; collection.approved_by_membership_id = actor.membership_id; collection.approved_at = _now()
    await db.commit(); await db.refresh(collection); return collection


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    org = actor.organization_id
    async def count(model, *where):
        return int(await db.scalar(select(func.count(model.id)).where(*where)) or 0)
    return {
        "approved_assets": await count(KnowledgeAsset, KnowledgeAsset.organization_id == org, KnowledgeAsset.status == KnowledgeAssetStatus.APPROVED),
        "drafts_in_review": await count(KnowledgeAsset, KnowledgeAsset.organization_id == org, KnowledgeAsset.status == KnowledgeAssetStatus.IN_REVIEW),
        "collections": await count(KnowledgeCollection, KnowledgeCollection.organization_id == org, KnowledgeCollection.status == KnowledgeCollectionStatus.ACTIVE),
        "approved_playbooks": await count(MatterPlaybook, MatterPlaybook.organization_id == org, MatterPlaybook.status == MatterPlaybookStatus.APPROVED),
        "authority_collections": await count(ResearchCollection, ResearchCollection.organization_id == org, ResearchCollection.status == ResearchCollectionStatus.APPROVED),
        "total_reuse_count": int(await db.scalar(select(func.coalesce(func.sum(KnowledgeAsset.usage_count), 0)).where(KnowledgeAsset.organization_id == org)) or 0),
    }
