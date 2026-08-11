from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.drafting import (
    DraftContextPreview,
    DraftFindingUpdate,
    DraftRenderResult,
    DraftSectionUpdate,
    DraftTemplateRead,
    LegalDraftCreate,
    LegalDraftListItem,
    LegalDraftRead,
    LegalDraftUpdate,
    LegalDraftVersionRead,
)
from app.services.drafting import service
from app.services.drafting.catalog import DRAFT_DEFINITIONS, get_draft_catalog

router = APIRouter(prefix="/drafting", tags=["legal-drafting"])


@router.get("/catalog")
async def drafting_catalog() -> list[dict]:
    return get_draft_catalog()


@router.get("/questionnaire/{draft_type}")
async def drafting_questionnaire(draft_type: str) -> dict:
    definition = DRAFT_DEFINITIONS.get(draft_type)
    if not definition:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Unknown legal draft type")
    return {
        "draft_type": draft_type,
        "name_en": definition["name_en"],
        "name_hi": definition["name_hi"],
        "description": definition["description"],
        "questions": definition["questions"],
        "sections": definition["sections"],
    }


@router.post("/templates/seed")
async def seed_templates(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    return {"created": await service.seed_templates(db)}


@router.get("/templates", response_model=list[DraftTemplateRead])
async def list_templates(db: AsyncSession = Depends(get_db)) -> list[DraftTemplateRead]:
    return [DraftTemplateRead.model_validate(item) for item in await service.list_templates(db)]


@router.get("/context/{matter_id}", response_model=DraftContextPreview)
async def context_preview(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DraftContextPreview:
    return DraftContextPreview.model_validate(await service.context_preview(db, matter_id))


@router.get("", response_model=list[LegalDraftListItem])
async def list_drafts(
    matter_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[LegalDraftListItem]:
    rows = await service.list_drafts(db, matter_id=matter_id, limit=limit, offset=offset)
    return [LegalDraftListItem.model_validate(row) for row in rows]


@router.post("", response_model=LegalDraftRead, status_code=status.HTTP_201_CREATED)
async def create_draft(
    payload: LegalDraftCreate,
    db: AsyncSession = Depends(get_db),
) -> LegalDraftRead:
    return LegalDraftRead.model_validate(await service.create_draft(db, payload))


@router.get("/{draft_id}", response_model=LegalDraftRead)
async def get_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> LegalDraftRead:
    return LegalDraftRead.model_validate(await service.get_draft(db, draft_id))


@router.patch("/{draft_id}", response_model=LegalDraftRead)
async def update_draft(
    draft_id: UUID,
    payload: LegalDraftUpdate,
    db: AsyncSession = Depends(get_db),
) -> LegalDraftRead:
    return LegalDraftRead.model_validate(await service.update_draft(db, draft_id, payload))


@router.post("/{draft_id}/regenerate", response_model=LegalDraftRead)
async def regenerate_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> LegalDraftRead:
    return LegalDraftRead.model_validate(await service.regenerate_draft(db, draft_id))


@router.patch("/{draft_id}/sections/{section_id}", response_model=LegalDraftRead)
async def update_section(
    draft_id: UUID,
    section_id: UUID,
    payload: DraftSectionUpdate,
    db: AsyncSession = Depends(get_db),
) -> LegalDraftRead:
    return LegalDraftRead.model_validate(
        await service.update_section(db, draft_id, section_id, payload)
    )


@router.patch("/{draft_id}/findings/{finding_id}", response_model=LegalDraftRead)
async def update_finding(
    draft_id: UUID,
    finding_id: UUID,
    payload: DraftFindingUpdate,
    db: AsyncSession = Depends(get_db),
) -> LegalDraftRead:
    return LegalDraftRead.model_validate(
        await service.update_finding(db, draft_id, finding_id, payload.status)
    )


@router.post("/{draft_id}/render", response_model=DraftRenderResult)
async def render_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DraftRenderResult:
    draft, version = await service.render_draft(db, draft_id)
    return DraftRenderResult(
        draft=LegalDraftRead.model_validate(draft),
        version=LegalDraftVersionRead.model_validate(version),
    )


@router.post("/{draft_id}/review", response_model=LegalDraftRead)
async def begin_review(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> LegalDraftRead:
    return LegalDraftRead.model_validate(await service.begin_review(db, draft_id))


@router.post("/{draft_id}/approve", response_model=DraftRenderResult)
async def approve_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DraftRenderResult:
    draft, version = await service.approve_draft(db, draft_id)
    return DraftRenderResult(
        draft=LegalDraftRead.model_validate(draft),
        version=LegalDraftVersionRead.model_validate(version),
    )


@router.get("/{draft_id}/versions", response_model=list[LegalDraftVersionRead])
async def list_versions(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[LegalDraftVersionRead]:
    return [LegalDraftVersionRead.model_validate(item) for item in await service.list_versions(db, draft_id)]


@router.get("/{draft_id}/download")
async def download_draft(
    draft_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    draft, path = await service.get_download_path(db, draft_id)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=draft.generated_filename or "legal-draft.docx",
    )
