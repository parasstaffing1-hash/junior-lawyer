from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.search import SearchEntityType
from app.schemas.search import (
    CommandDefinition,
    RecentItemCreate,
    RecentItemRead,
    SavedSearchCreate,
    SavedSearchRead,
    SearchPreferenceRead,
    SearchPreferenceUpdate,
    UniversalSearchResponse, SearchIndexJobRead, SearchIndexHealth, SearchDuplicateItem,
)
from app.services.search import service
from app.services.search_index import service as index_service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/search", tags=["universal-search"])


@router.get("", response_model=UniversalSearchResponse)
async def search(
    q: str = Query(min_length=1, max_length=1000),
    scopes: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    include_corpus: bool = True,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
):
    parsed: set[SearchEntityType] | None = None
    if scopes:
        parsed = set()
        for raw in scopes.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed.add(SearchEntityType(raw))
            except ValueError:
                continue
    return UniversalSearchResponse(**await service.universal_search(db, actor, q, scopes=parsed, limit=limit, include_corpus=include_corpus))


@router.get("/commands", response_model=list[CommandDefinition])
async def commands(q: str | None = Query(default=None, max_length=300), actor: ActorContext = Depends(require_actor)):
    return [CommandDefinition(**row) for row in service.list_commands(q)]


@router.get("/preferences", response_model=SearchPreferenceRead)
async def preferences(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SearchPreferenceRead.model_validate(await service.get_preferences(db, actor))


@router.patch("/preferences", response_model=SearchPreferenceRead)
async def patch_preferences(payload: SearchPreferenceUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SearchPreferenceRead.model_validate(await service.update_preferences(db, actor, payload.model_dump(exclude_unset=True)))


@router.get("/saved", response_model=list[SavedSearchRead])
async def saved(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [SavedSearchRead.model_validate(row) for row in await service.list_saved_searches(db, actor)]


@router.post("/saved", response_model=SavedSearchRead, status_code=201)
async def save(payload: SavedSearchCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SavedSearchRead.model_validate(await service.create_saved_search(db, actor, payload))


@router.post("/saved/{search_id}/run", response_model=SavedSearchRead)
async def run_saved(search_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SavedSearchRead.model_validate(await service.mark_saved_search_run(db, actor, search_id))


@router.delete("/saved/{search_id}", status_code=204)
async def delete_saved(search_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    await service.delete_saved_search(db, actor, search_id)
    return Response(status_code=204)


@router.get("/recent", response_model=list[RecentItemRead])
async def recent(limit: int = Query(12, ge=1, le=50), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [RecentItemRead.model_validate(row) for row in await service.list_recent(db, actor, limit)]


@router.post("/recent", response_model=RecentItemRead, status_code=201)
async def record_recent(payload: RecentItemCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return RecentItemRead.model_validate(await service.record_recent(db, actor, payload))


@router.post("/index/rebuild", response_model=SearchIndexJobRead)
async def rebuild_search_index(
    include_corpus: bool = True, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db),
):
    return SearchIndexJobRead.model_validate(await index_service.rebuild_organization_index(db, actor, include_corpus=include_corpus))


@router.get("/index/health", response_model=SearchIndexHealth)
async def search_index_health(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SearchIndexHealth(**await index_service.health(db, actor))


@router.post("/index/duplicates/detect")
async def detect_search_duplicates(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return {"created": await index_service.detect_duplicates(db, actor)}


@router.get("/index/duplicates", response_model=list[SearchDuplicateItem])
async def search_duplicates(limit: int = Query(100, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [SearchDuplicateItem(**row) for row in await index_service.list_duplicates(db, actor, limit=limit)]


@router.post("/index/documents/{document_id}")
async def incremental_document_index(document_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    # Document access remains enforced by the document service on normal ingestion; this endpoint is admin/partner maintenance.
    if getattr(actor.role, "value", str(actor.role)) not in {"owner", "admin", "partner"}:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Partner, admin or owner role required")
    return await index_service.reindex_document(db, document_id)
