from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.contract import ContractType
from app.models.contract_review import ReviewFindingStatus
from app.schemas.contract_review import (
    ClauseDecisionUpdate,
    ContractReviewListItem,
    ContractReviewRead,
    FindingUpdate,
    PlaybookCreate,
    PlaybookRead,
    RedlineRead,
    ReviewStats,
)
from app.services.contracts import review as review_service

router = APIRouter(prefix="/contract-reviews", tags=["contract-reviews"])


@router.get("/playbooks", response_model=list[PlaybookRead])
async def list_playbooks(db: AsyncSession = Depends(get_db)) -> list[PlaybookRead]:
    rows = await review_service.list_playbooks(db)
    return [PlaybookRead.model_validate(row) for row in rows]


@router.post("/playbooks/seed")
async def seed_playbooks(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    return {"created": await review_service.seed_default_playbooks(db)}


@router.post("/playbooks", response_model=PlaybookRead, status_code=201)
async def create_playbook(payload: PlaybookCreate, db: AsyncSession = Depends(get_db)) -> PlaybookRead:
    return PlaybookRead.model_validate(await review_service.create_playbook(db, payload))


@router.get("/stats", response_model=ReviewStats)
async def review_stats(db: AsyncSession = Depends(get_db)) -> ReviewStats:
    return await review_service.get_stats(db)


@router.get("", response_model=list[ContractReviewListItem])
async def list_reviews(
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[ContractReviewListItem]:
    return await review_service.list_reviews(db, limit=limit)


@router.post("", response_model=ContractReviewRead, status_code=201)
async def create_review(
    file: UploadFile = File(...),
    contract_type: ContractType = Form(...),
    title: str = Form(..., min_length=2, max_length=350),
    counterparty_name: str | None = Form(default=None),
    matter_id: UUID | None = Form(default=None),
    internal_contract_id: UUID | None = Form(default=None),
    playbook_id: UUID | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> ContractReviewRead:
    review = await review_service.create_review_from_upload(
        db,
        upload=file,
        contract_type=contract_type,
        title=title,
        counterparty_name=counterparty_name,
        matter_id=matter_id,
        internal_contract_id=internal_contract_id,
        playbook_id=playbook_id,
    )
    return ContractReviewRead.model_validate(review)


@router.get("/{review_id}", response_model=ContractReviewRead)
async def get_review(review_id: UUID, db: AsyncSession = Depends(get_db)) -> ContractReviewRead:
    return ContractReviewRead.model_validate(await review_service.get_review(db, review_id))


@router.post("/{review_id}/reanalyze", response_model=ContractReviewRead)
async def reanalyze_review(review_id: UUID, db: AsyncSession = Depends(get_db)) -> ContractReviewRead:
    return ContractReviewRead.model_validate(await review_service.reanalyze_review(db, review_id))


@router.patch("/{review_id}/findings/{finding_id}", response_model=ContractReviewRead)
async def update_finding(
    review_id: UUID,
    finding_id: UUID,
    payload: FindingUpdate,
    db: AsyncSession = Depends(get_db),
) -> ContractReviewRead:
    return ContractReviewRead.model_validate(
        await review_service.update_finding_status(db, review_id, finding_id, payload.status)
    )


@router.patch("/{review_id}/clauses/{clause_id}/decision", response_model=ContractReviewRead)
async def update_clause_decision(
    review_id: UUID,
    clause_id: UUID,
    payload: ClauseDecisionUpdate,
    db: AsyncSession = Depends(get_db),
) -> ContractReviewRead:
    return ContractReviewRead.model_validate(
        await review_service.update_clause_decision(db, review_id, clause_id, payload.decision)
    )


@router.post("/{review_id}/redlines", response_model=RedlineRead, status_code=201)
async def generate_redline(review_id: UUID, db: AsyncSession = Depends(get_db)) -> RedlineRead:
    return RedlineRead.model_validate(await review_service.generate_redline(db, review_id))


@router.get("/{review_id}/redlines/{redline_id}/download")
async def download_redline(
    review_id: UUID,
    redline_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    version, path = await review_service.get_redline_path(db, review_id, redline_id)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=version.generated_filename,
    )
