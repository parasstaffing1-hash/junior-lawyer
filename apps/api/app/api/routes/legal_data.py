from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.legal_data import (
    AlertStatusRequest,
    AmendmentRead,
    AmendmentReviewRequest,
    CorpusCheckpointRead,
    IngestionRunDetail,
    IngestionRunRead,
    IntegrityCheckRead,
    JurisdictionPackCreate,
    JurisdictionPackRead,
    JurisdictionReleaseCreate,
    JurisdictionReleaseRead,
    LegalDataAlertRead,
    LegalDataDashboard,
    LegalDataFeedCreate,
    LegalDataFeedRead,
    LegalDataFeedUpdate,
    LegalDataManifest,
)
from app.services.legal_data import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/legal-data", tags=["legal-data-operations"])


@router.get("/dashboard", response_model=LegalDataDashboard)
async def dashboard(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.dashboard(db, actor)


@router.get("/feeds", response_model=list[LegalDataFeedRead])
async def feeds(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_feeds(db, actor)


@router.post("/feeds", response_model=LegalDataFeedRead)
async def create_feed(payload: LegalDataFeedCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_feed(db, actor, payload)


@router.patch("/feeds/{feed_id}", response_model=LegalDataFeedRead)
async def update_feed(feed_id: UUID, payload: LegalDataFeedUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.update_feed(db, actor, feed_id, payload)


@router.post("/feeds/{feed_id}/ingest", response_model=IngestionRunDetail)
async def ingest(feed_id: UUID, payload: LegalDataManifest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.ingest_manifest(db, actor, feed_id, payload)


@router.post("/feeds/{feed_id}/sync")
async def sync(feed_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.sync_feed(db, actor, feed_id)


@router.get("/runs", response_model=list[IngestionRunRead])
async def runs(limit: int = Query(default=100, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_runs(db, actor, limit=limit)


@router.get("/runs/{run_id}", response_model=IngestionRunDetail)
async def run_detail(run_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.run_detail(db, actor, run_id)


@router.get("/amendments", response_model=list[AmendmentRead])
async def amendments(status: str | None = None, limit: int = Query(default=200, ge=1, le=1000), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_amendments(db, actor, status=status, limit=limit)


@router.patch("/amendments/{amendment_id}", response_model=AmendmentRead)
async def review_amendment(amendment_id: UUID, payload: AmendmentReviewRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.review_amendment(db, actor, amendment_id, payload)


@router.post("/integrity/sweep")
async def integrity_sweep(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.integrity_sweep(db, actor)


@router.get("/integrity", response_model=list[IntegrityCheckRead])
async def integrity(limit: int = Query(default=300, ge=1, le=2000), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_integrity_checks(db, actor, limit=limit)


@router.get("/alerts", response_model=list[LegalDataAlertRead])
async def alerts(status: str | None = None, limit: int = Query(default=200, ge=1, le=1000), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_alerts(db, actor, status=status, limit=limit)


@router.patch("/alerts/{alert_id}", response_model=LegalDataAlertRead)
async def alert_status(alert_id: UUID, payload: AlertStatusRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.update_alert_status(db, actor, alert_id, payload)


@router.get("/checkpoints", response_model=list[CorpusCheckpointRead])
async def checkpoints(limit: int = Query(default=50, ge=1, le=500), actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_checkpoints(db, actor, limit=limit)


@router.get("/packs", response_model=list[JurisdictionPackRead])
async def packs(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_packs(db, actor)


@router.post("/packs", response_model=JurisdictionPackRead)
async def create_pack(payload: JurisdictionPackCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_pack(db, actor, payload)


@router.get("/packs/{pack_id}/releases", response_model=list[JurisdictionReleaseRead])
async def releases(pack_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.list_pack_releases(db, actor, pack_id)


@router.post("/packs/{pack_id}/releases", response_model=JurisdictionReleaseRead)
async def create_release(pack_id: UUID, payload: JurisdictionReleaseCreate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.create_pack_release(db, actor, pack_id, payload)


@router.post("/releases/{release_id}/activate", response_model=JurisdictionReleaseRead)
async def activate_release(release_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return await service.activate_pack_release(db, actor, release_id)

# --- Bare Acts (KanoonGPT) Endpoints ---

from app.services.bare_acts_service import bare_acts_service

@router.get("/bare-acts")
async def get_bare_acts(db: AsyncSession = Depends(get_db)):
    """Get all available Bare Acts for the library."""
    return await bare_acts_service.get_all_acts(db)

@router.get("/bare-acts/search")
async def search_bare_acts(q: str, db: AsyncSession = Depends(get_db)):
    """Search across all Bare Acts sections."""
    return await bare_acts_service.search_sections(db, q)

@router.get("/bare-acts/{act_id}")
async def get_bare_act(act_id: str, db: AsyncSession = Depends(get_db)):
    """Get full details and sections of a specific Bare Act."""
    act = await bare_acts_service.get_act_by_id(db, act_id)
    if not act:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Bare Act not found")
    return act
