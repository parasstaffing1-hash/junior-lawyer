from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.drafting import (
    DraftPreview,
    DraftSendRequest,
    DraftSendResult,
    DraftLibrary,
    DraftLibraryCategory,
    DraftLibraryItem,
    DraftCatalogItem,
    DraftContextPreview,
    DraftQuestion,
    DraftQuestionnaire,
    DraftSectionDefinition,
    TemplateSeedResult,
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
from app.models.drafting import LegalDraftStatus
from app.services.drafting import dispatch, library, service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor
from app.services.drafting.catalog import DRAFT_DEFINITIONS, get_draft_catalog

router = APIRouter(prefix="/drafting", tags=["legal-drafting"])


@router.get("/catalog", response_model=list[DraftCatalogItem])
async def drafting_catalog() -> list[DraftCatalogItem]:
    return [DraftCatalogItem.model_validate(item) for item in get_draft_catalog()]


@router.get("/questionnaire/{draft_type}", response_model=DraftQuestionnaire)
async def drafting_questionnaire(draft_type: str) -> DraftQuestionnaire:
    definition = DRAFT_DEFINITIONS.get(draft_type)
    if not definition:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Unknown legal draft type")
    return DraftQuestionnaire(
        draft_type=draft_type,
        name_en=definition["name_en"],
        name_hi=definition["name_hi"],
        description=definition["description"],
        questions=[DraftQuestion.model_validate(item) for item in definition["questions"]],
        sections=[DraftSectionDefinition.model_validate(item) for item in definition["sections"]],
    )


@router.post("/templates/seed", response_model=TemplateSeedResult)
async def seed_templates(db: AsyncSession = Depends(get_db)) -> TemplateSeedResult:
    return TemplateSeedResult(created=await service.seed_templates(db))


@router.get("/library", response_model=DraftLibrary)
async def draft_library(
    category: str | None = None,
    forum: str | None = None,
    search: str | None = None,
) -> DraftLibrary:
    """The instrument-level catalogue: what can actually be drafted."""
    rows = library.list_templates(category=category, forum=forum, search=search)
    counts: dict[str, int] = {}
    for entry in library.list_templates():
        counts[entry["category"]] = counts.get(entry["category"], 0) + 1
    return DraftLibrary(
        categories=[
            DraftLibraryCategory(
                key=key,
                name_en=value["name_en"],
                name_hi=value["name_hi"],
                template_count=counts.get(key, 0),
            )
            for key, value in library.CATEGORIES.items()
        ],
        templates=[DraftLibraryItem(**row) for row in rows],
        total=len(rows),
    )


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


@router.get("/{draft_id}/email-preview", response_model=DraftPreview)
async def preview_draft_email(
    draft_id: UUID,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> DraftPreview:
    """Exactly what would be sent, and whether it may be sent at all."""
    draft = await service.get_draft(db, draft_id)
    approved = draft.status == LegalDraftStatus.APPROVED
    return DraftPreview(
        subject=draft.title or "Legal draft",
        body=dispatch.render_plain_text(draft),
        draft_status=draft.status.value,
        sendable=approved,
        blocked_reason=(
            None if approved
            else f"Draft is '{draft.status.value}'. Only an approved draft can be sent."
        ),
    )


@router.post("/{draft_id}/send", response_model=DraftSendResult)
async def send_draft(
    draft_id: UUID,
    payload: DraftSendRequest,
    actor: ActorContext = Depends(require_actor),
    db: AsyncSession = Depends(get_db),
) -> DraftSendResult:
    """Email an approved draft to a client, opposite party or court."""
    result = await dispatch.send_draft(
        db,
        actor,
        draft_id,
        to=payload.to,
        recipient_kind=payload.recipient_kind,
        subject=payload.subject,
        covering_note=payload.covering_note,
        cc=payload.cc,
        bcc=payload.bcc,
        reply_to=payload.reply_to,
        connection_id=payload.connection_id,
        confirm=payload.confirm,
    )
    return DraftSendResult(**result)
