from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.document import ProcessingStatus
from app.models.document_entity import EntityType
from app.schemas.document import (
    DocumentEntityRead,
    DocumentPageRead,
    DocumentPageWindowRead,
    DocumentPageMatchRead,
    DocumentRead,
    DocumentSuggestionRead,
    DocumentTextRead,
)
from app.services.documents import service
from app.services.documents.storage import resolve_storage_key
from app.core.config import settings
from app.models.jobs import JobKind, JobPriority
from app.services.jobs import service as jobs_service
from app.models.security import DocumentAccessLevel
from app.services.security.context import get_current_actor
from app.services.security.permissions import decide_document_access

router = APIRouter(tags=["documents"])


@router.post(
    "/matters/{matter_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    matter_id: UUID,
    file: UploadFile = File(...),
    ocr: bool = Query(default=True, description="Use local Hindi+English OCR when needed"),
    background: bool | None = Query(default=None, description="Queue OCR/extraction instead of blocking the request"),
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    use_background = settings.background_jobs_enabled if background is None else background
    actor = get_current_actor()
    if use_background and actor is None:
        raise HTTPException(status_code=401, detail="Background processing requires an authenticated organization user")
    document = await service.upload_document(db, matter_id=matter_id, upload=file, allow_ocr=ocr, process_now=not use_background)
    if use_background and actor is not None:
        first = await jobs_service.enqueue(db, actor, kind=JobKind.DOCUMENT_REPROCESS, payload={"document_id": str(document.id), "allow_ocr": ocr}, priority=JobPriority.NORMAL, matter_id=matter_id, resource_type="document", resource_id=document.id, idempotency_key=f"process:{document.id}:{document.sha256}")
        intel = await jobs_service.enqueue(db, actor, kind=JobKind.MATTER_INTELLIGENCE_REBUILD, payload={"matter_id": str(matter_id)}, matter_id=matter_id, resource_type="matter", resource_id=matter_id, depends_on=[first.id])
        await jobs_service.enqueue(db, actor, kind=JobKind.SEARCH_DOCUMENT_REINDEX, payload={"document_id": str(document.id)}, matter_id=matter_id, resource_type="document", resource_id=document.id, depends_on=[first.id])
    return document


@router.get("/matters/{matter_id}/documents", response_model=list[DocumentRead])
async def list_documents(
    matter_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[DocumentRead]:
    return await service.list_documents(db, matter_id)


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    document = await service.get_document(db, document_id)
    return service.to_document_read(document)


@router.get("/documents/{document_id}/pages", response_model=list[DocumentPageRead])
async def get_document_pages(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[DocumentPageRead]:
    return await service.get_pages(db, document_id)


@router.get("/documents/{document_id}/page-window", response_model=DocumentPageWindowRead)
async def get_document_page_window(
    document_id: UUID,
    start_page: int = Query(1, ge=1),
    limit: int = Query(8, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
) -> DocumentPageWindowRead:
    document, pages = await service.get_page_window(db, document_id, start_page=start_page, limit=limit)
    total = document.page_count or 0
    end_page = pages[-1].page_number if pages else min(start_page, total)
    return DocumentPageWindowRead(
        document_id=document.id, filename=document.filename, total_pages=total, start_page=start_page, end_page=end_page,
        has_previous=start_page > 1, has_next=end_page < total, pages=pages,
    )


@router.get("/documents/{document_id}/find", response_model=list[DocumentPageMatchRead])
async def find_document_text(
    document_id: UUID,
    q: str = Query(min_length=1, max_length=300),
    limit: int = Query(40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentPageMatchRead]:
    return [DocumentPageMatchRead(**row) for row in await service.find_in_document(db, document_id, q, limit=limit)]


@router.get("/documents/{document_id}/entities", response_model=list[DocumentEntityRead])
async def get_document_entities(
    document_id: UUID,
    entity_type: EntityType | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentEntityRead]:
    return await service.get_entities(db, document_id, entity_type=entity_type)


@router.get("/documents/{document_id}/text", response_model=DocumentTextRead)
async def get_document_text(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentTextRead:
    document, text = await service.get_text(db, document_id)
    return DocumentTextRead(
        document_id=document.id,
        filename=document.filename,
        page_count=document.page_count or 0,
        text=text,
    )


@router.get("/documents/{document_id}/suggestions", response_model=DocumentSuggestionRead)
async def get_document_suggestions(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentSuggestionRead:
    return await service.get_suggestions(db, document_id)


@router.get("/documents/{document_id}/file")
async def download_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    document = await service.get_document(db, document_id)
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_document_access(db, actor, document_id, required=DocumentAccessLevel.DOWNLOAD)
        if not decision.allowed:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail=decision.reason)
    if not document.storage_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Stored file not found")
    path = resolve_storage_key(document.storage_key)
    return FileResponse(path, media_type=document.mime_type, filename=document.filename)


@router.post("/documents/{document_id}/reprocess", response_model=DocumentRead)
async def reprocess_document(
    document_id: UUID,
    ocr: bool = Query(default=True),
    background: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    if not background:
        document = await service.process_document(db, document_id, allow_ocr=ocr)
        return service.to_document_read(document)
    actor=get_current_actor()
    if actor is None: raise HTTPException(status_code=401,detail="Background processing requires authentication")
    document=await service.get_document(db,document_id)
    document.processing_status=ProcessingStatus.PENDING; document.processing_error=None; await db.commit(); await db.refresh(document)
    first=await jobs_service.enqueue(db,actor,kind=JobKind.DOCUMENT_REPROCESS,payload={"document_id":str(document_id),"allow_ocr":ocr},matter_id=document.matter_id,resource_type="document",resource_id=document.id)
    intel=await jobs_service.enqueue(db,actor,kind=JobKind.MATTER_INTELLIGENCE_REBUILD,payload={"matter_id":str(document.matter_id)},matter_id=document.matter_id,resource_type="matter",resource_id=document.matter_id,depends_on=[first.id])
    await jobs_service.enqueue(db,actor,kind=JobKind.SEARCH_DOCUMENT_REINDEX,payload={"document_id":str(document.id)},matter_id=document.matter_id,resource_type="document",resource_id=document.id,depends_on=[first.id])
    return service.to_document_read(await service.get_document(db,document_id))


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    await service.delete_document(db, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
