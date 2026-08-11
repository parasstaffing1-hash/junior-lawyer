from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.knowledge import KnowledgeAssetKind, KnowledgeAssetStatus, SanitizationStatus
from app.schemas.knowledge import (
    AnnotationCreate, AnnotationRead, KnowledgeAssetCreate, KnowledgeAssetDetail, KnowledgeAssetRead,
    KnowledgeAssetUpdate, KnowledgeCollectionCreate, KnowledgeCollectionRead, KnowledgeDashboard,
    KnowledgeReviewRequest, KnowledgeSearchResponse, KnowledgeSearchResult, KnowledgeVersionRead,
    MatterPlaybookCreate, MatterPlaybookItemCreate, MatterPlaybookItemRead, MatterPlaybookRead,
    PromoteContractClauseRequest, PromoteDraftSectionRequest, ResearchCollectionCreate,
    ResearchCollectionItemCreate, ResearchCollectionItemRead, ResearchCollectionRead,
)
from app.services.knowledge import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor
from app.services.security.permissions import decide_matter_access

router = APIRouter(prefix="/knowledge", tags=["firm-knowledge"])


async def _safe_asset_read(db: AsyncSession, actor: ActorContext, row) -> KnowledgeAssetRead:
    out = KnowledgeAssetRead.model_validate(row)
    if out.source_matter_id:
        decision = await decide_matter_access(db, actor, out.source_matter_id)
        if not decision.allowed:
            out = out.model_copy(update={"source_matter_id": None})
    return out


@router.get("/dashboard", response_model=KnowledgeDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KnowledgeDashboard(**await service.dashboard(db, actor))


@router.get("/collections", response_model=list[KnowledgeCollectionRead])
async def collections(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [KnowledgeCollectionRead.model_validate(r) for r in await service.list_collections(db, actor)]


@router.post("/collections", response_model=KnowledgeCollectionRead, status_code=201)
async def create_collection(payload: KnowledgeCollectionCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KnowledgeCollectionRead.model_validate(await service.create_collection(db, actor, payload))


@router.get("/assets", response_model=list[KnowledgeAssetRead])
async def assets(status: KnowledgeAssetStatus | None = None, kind: KnowledgeAssetKind | None = None, limit: int = Query(200, ge=1, le=1000), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    rows = await service.list_assets(db, actor, status=status, kind=kind, limit=limit)
    return [await _safe_asset_read(db, actor, r) for r in rows]


@router.post("/assets", response_model=KnowledgeAssetRead, status_code=201)
async def create_asset(payload: KnowledgeAssetCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KnowledgeAssetRead.model_validate(await service.create_asset(db, actor, payload))


@router.get("/assets/{asset_id}", response_model=KnowledgeAssetDetail)
async def asset(asset_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    detail = await service.asset_detail(db, actor, asset_id)
    safe = await _safe_asset_read(db, actor, detail["asset"])
    return KnowledgeAssetDetail(**safe.model_dump(), sources=detail["sources"], tags=detail["tags"], source_access_restricted=detail["source_access_restricted"])


@router.patch("/assets/{asset_id}", response_model=KnowledgeAssetRead)
async def patch_asset(asset_id: UUID, payload: KnowledgeAssetUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KnowledgeAssetRead.model_validate(await service.update_asset(db, actor, asset_id, payload))


@router.post("/assets/{asset_id}/submit", response_model=KnowledgeAssetRead)
async def submit(asset_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KnowledgeAssetRead.model_validate(await service.submit_for_review(db, actor, asset_id))


@router.post("/assets/{asset_id}/approve", response_model=KnowledgeAssetRead)
async def approve(asset_id: UUID, payload: KnowledgeReviewRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KnowledgeAssetRead.model_validate(await service.approve_asset(db, actor, asset_id, sanitization_status=payload.sanitization_status, review_note=payload.review_note))


@router.post("/assets/{asset_id}/retire", response_model=KnowledgeAssetRead)
async def retire(asset_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KnowledgeAssetRead.model_validate(await service.retire_asset(db, actor, asset_id))


@router.get("/assets/{asset_id}/versions", response_model=list[KnowledgeVersionRead])
async def versions(asset_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [KnowledgeVersionRead.model_validate(r) for r in await service.versions(db, actor, asset_id)]


@router.get("/assets/{asset_id}/annotations", response_model=list[AnnotationRead])
async def annotations(asset_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [AnnotationRead.model_validate(r) for r in await service.annotations(db, actor, asset_id)]


@router.post("/assets/{asset_id}/annotations", response_model=AnnotationRead, status_code=201)
async def add_annotation(asset_id: UUID, payload: AnnotationCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return AnnotationRead.model_validate(await service.add_annotation(db, actor, asset_id, payload))


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search(q: str = Query(min_length=2, max_length=500), kind: KnowledgeAssetKind | None = None, practice_area: str | None = None, limit: int = Query(25, ge=1, le=100), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    data = await service.search_assets(db, actor, q, kind=kind, practice_area=practice_area, limit=limit)
    results = []
    for x in data["results"]:
        safe = await _safe_asset_read(db, actor, x["asset"])
        results.append(KnowledgeSearchResult(asset=safe, score=x["score"], lexical_score=x["lexical_score"], quality_score=x["quality_score"], snippet=x["snippet"], tags=x["tags"]))
    return KnowledgeSearchResponse(query=data["query"], normalized_query=data["normalized_query"], result_count=len(results), results=results)


@router.post("/promote/draft-section", response_model=KnowledgeAssetRead, status_code=201)
async def promote_draft_section(payload: PromoteDraftSectionRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KnowledgeAssetRead.model_validate(await service.promote_draft_section(db, actor, payload))


@router.post("/promote/contract-clause", response_model=KnowledgeAssetRead, status_code=201)
async def promote_contract_clause(payload: PromoteContractClauseRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return KnowledgeAssetRead.model_validate(await service.promote_contract_clause(db, actor, payload))


@router.get("/playbooks", response_model=list[MatterPlaybookRead])
async def playbooks(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [MatterPlaybookRead.model_validate(r) for r in await service.list_playbooks(db, actor)]


@router.post("/playbooks", response_model=MatterPlaybookRead, status_code=201)
async def create_playbook(payload: MatterPlaybookCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return MatterPlaybookRead.model_validate(await service.create_playbook(db, actor, payload))


@router.get("/playbooks/{playbook_id}/items", response_model=list[MatterPlaybookItemRead])
async def playbook_items(playbook_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [MatterPlaybookItemRead.model_validate(r) for r in await service.playbook_items(db, actor, playbook_id)]


@router.post("/playbooks/{playbook_id}/items", response_model=MatterPlaybookItemRead, status_code=201)
async def add_playbook_item(playbook_id: UUID, payload: MatterPlaybookItemCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return MatterPlaybookItemRead.model_validate(await service.add_playbook_item(db, actor, playbook_id, payload))


@router.post("/playbooks/{playbook_id}/approve", response_model=MatterPlaybookRead)
async def approve_playbook(playbook_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return MatterPlaybookRead.model_validate(await service.approve_playbook(db, actor, playbook_id))


@router.get("/authority-collections", response_model=list[ResearchCollectionRead])
async def authority_collections(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ResearchCollectionRead.model_validate(r) for r in await service.list_research_collections(db, actor)]


@router.post("/authority-collections", response_model=ResearchCollectionRead, status_code=201)
async def create_authority_collection(payload: ResearchCollectionCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ResearchCollectionRead.model_validate(await service.create_research_collection(db, actor, payload))


@router.get("/authority-collections/{collection_id}/items", response_model=list[ResearchCollectionItemRead])
async def authority_items(collection_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [ResearchCollectionItemRead.model_validate(r) for r in await service.research_items(db, actor, collection_id)]


@router.post("/authority-collections/{collection_id}/items", response_model=ResearchCollectionItemRead, status_code=201)
async def add_authority_item(collection_id: UUID, payload: ResearchCollectionItemCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ResearchCollectionItemRead.model_validate(await service.add_research_item(db, actor, collection_id, payload))


@router.post("/authority-collections/{collection_id}/approve", response_model=ResearchCollectionRead)
async def approve_authority_collection(collection_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return ResearchCollectionRead.model_validate(await service.approve_research_collection(db, actor, collection_id))
