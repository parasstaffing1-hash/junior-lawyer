from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentLanguage, ProcessingStatus
from app.models.document_entity import DocumentEntity, EntityType
from app.models.document_page import DocumentPage
from app.models.matter import Matter
from app.models.security import DocumentAccessLevel, MatterAccessLevel
from app.services.security.context import get_current_actor
from app.services.security.permissions import decide_document_access, enforce_current_matter_access
from app.schemas.document import DocumentRead, DocumentSuggestionRead
from app.services.documents.extractor import DocumentExtractionError, extract_document
from app.services.documents.metadata import extract_entities
from app.services.documents.storage import (
    delete_storage_key,
    discard_staged,
    promote_upload,
    resolve_storage_key,
    stage_upload,
)
from app.services.language.detector import detect_language

logger = logging.getLogger(__name__)


def _to_language(value: str) -> DocumentLanguage:
    try:
        return DocumentLanguage(value)
    except ValueError:
        return DocumentLanguage.UNKNOWN


def _entity_counts(document: Document) -> dict[str, int]:
    counts = Counter(entity.entity_type.value for entity in document.entities)
    return dict(sorted(counts.items()))


def to_document_read(document: Document) -> DocumentRead:
    response = DocumentRead.model_validate(document)
    response.entity_counts = _entity_counts(document)
    return response


async def _get_matter(
    db: AsyncSession,
    matter_id: UUID,
    *,
    required: MatterAccessLevel = MatterAccessLevel.VIEW,
) -> Matter:
    matter = await db.get(Matter, matter_id)
    if matter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    await enforce_current_matter_access(db, matter_id, required=required)
    return matter


async def get_document(db: AsyncSession, document_id: UUID) -> Document:
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.pages), selectinload(Document.entities))
        .execution_options(populate_existing=True)
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_document_access(db, actor, document_id, required=DocumentAccessLevel.VIEW)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    return document


async def list_documents(db: AsyncSession, matter_id: UUID) -> list[DocumentRead]:
    await _get_matter(db, matter_id)
    stmt = (
        select(Document)
        .where(Document.matter_id == matter_id)
        .options(selectinload(Document.entities))
        .order_by(Document.created_at.desc())
    )
    documents = (await db.scalars(stmt)).unique().all()
    return [to_document_read(document) for document in documents]


async def upload_document(
    db: AsyncSession,
    *,
    matter_id: UUID,
    upload: UploadFile,
    allow_ocr: bool = True,
    process_now: bool = True,
) -> DocumentRead:
    await _get_matter(db, matter_id, required=MatterAccessLevel.WORK)
    staged = await stage_upload(upload)

    duplicate_stmt = select(Document).where(
        Document.matter_id == matter_id,
        Document.sha256 == staged.sha256,
    )
    duplicate = (await db.execute(duplicate_stmt)).scalar_one_or_none()
    if duplicate is not None:
        discard_staged(staged)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This exact file already exists in the matter",
                "duplicate_document_id": str(duplicate.id),
                "sha256": staged.sha256,
            },
        )

    document = Document(
        id=uuid4(),
        matter_id=matter_id,
        filename=staged.original_filename,
        display_name=Path(staged.safe_filename).stem,
        file_extension=staged.extension,
        mime_type=staged.mime_type,
        size_bytes=staged.size_bytes,
        sha256=staged.sha256,
        processing_status=ProcessingStatus.PROCESSING if process_now else ProcessingStatus.PENDING,
    )

    try:
        document.storage_key = promote_upload(
            staged,
            matter_id=matter_id,
            document_id=document.id,
        )
        db.add(document)
        await db.commit()
    except Exception:
        discard_staged(staged)
        delete_storage_key(document.storage_key)
        await db.rollback()
        raise

    if process_now:
        document = await process_document(db, document.id, allow_ocr=allow_ocr)
    else:
        document = await get_document(db, document.id)
    return to_document_read(document)


async def process_document(
    db: AsyncSession,
    document_id: UUID,
    *,
    allow_ocr: bool = True,
    rebuild_intelligence: bool = True,
    reindex_search: bool = True,
) -> Document:
    document = await get_document(db, document_id)
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_document_access(db, actor, document_id, required=DocumentAccessLevel.EDIT)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    if not document.storage_key or not document.file_extension:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document has no stored file to process",
        )

    document.processing_status = ProcessingStatus.PROCESSING
    document.processing_error = None
    await db.commit()

    path = resolve_storage_key(document.storage_key)
    if not path.exists():
        document.processing_status = ProcessingStatus.FAILED
        document.processing_error = "Stored file is missing"
        await db.commit()
        return await get_document(db, document_id)

    try:
        result = await asyncio.to_thread(
            extract_document,
            path,
            document.file_extension,
            allow_ocr=allow_ocr,
        )

        # Reprocessing is replace-in-place: source file remains immutable, derived rows are rebuilt.
        await db.execute(delete(DocumentEntity).where(DocumentEntity.document_id == document.id))
        await db.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
        await db.flush()

        all_text: list[str] = []
        for extracted_page in result.pages:
            text = extracted_page.text
            all_text.append(text)
            page_language = _to_language(detect_language(text).language)
            page_model = DocumentPage(
                document_id=document.id,
                page_number=extracted_page.page_number,
                text=text,
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                char_count=len(text),
                detected_language=page_language,
                extraction_method=extracted_page.extraction_method,
                is_scanned=extracted_page.is_scanned,
            )
            db.add(page_model)
            await db.flush()

            for extracted_entity in extract_entities(text):
                db.add(
                    DocumentEntity(
                        document_id=document.id,
                        page_id=page_model.id,
                        page_number=extracted_page.page_number,
                        entity_type=extracted_entity.entity_type,
                        raw_text=extracted_entity.raw_text,
                        normalized_value=extracted_entity.normalized_value,
                        confidence=extracted_entity.confidence,
                        start_char=extracted_entity.start_char,
                        end_char=extracted_entity.end_char,
                        metadata_json=extracted_entity.metadata,
                    )
                )

        combined_text = "\n\n".join(all_text)
        document.page_count = len(result.pages)
        document.text_char_count = len(combined_text)
        document.detected_language = _to_language(detect_language(combined_text[:250_000]).language)
        document.extraction_method = result.extraction_method
        document.is_scanned = result.is_scanned
        document.ocr_used = result.ocr_used
        document.extracted_at = datetime.now(timezone.utc)
        document.processing_status = ProcessingStatus.READY
        document.processing_error = None
        await db.commit()
    except (DocumentExtractionError, OSError, ValueError) as exc:
        await db.rollback()
        document = await get_document(db, document_id)
        document.processing_status = ProcessingStatus.FAILED
        document.processing_error = str(exc)[:4000]
        await db.commit()
    except Exception as exc:
        await db.rollback()
        document = await get_document(db, document_id)
        document.processing_status = ProcessingStatus.FAILED
        document.processing_error = f"Unexpected processing error: {exc}"[:4000]
        await db.commit()

    final_document = await get_document(db, document_id)
    if final_document.processing_status == ProcessingStatus.READY:
        # Matter intelligence is deterministic and cheap enough to rebuild after ingestion for v1.
        # Failure here must never turn a successfully extracted source document into a failed document.
        if rebuild_intelligence:
            try:
                from app.services.intelligence.service import rebuild_matter_intelligence

                await rebuild_matter_intelligence(db, final_document.matter_id)
            except Exception:
                logger.exception("Matter-intelligence rebuild failed after document processing")
        if reindex_search:
            # Batch 19: update only this document's materialized search chunks.
            try:
                from app.services.search_index.service import reindex_document
                await reindex_document(db, final_document.id)
            except Exception:
                logger.exception("Incremental search reindex failed after document processing")
    return final_document


async def get_pages(db: AsyncSession, document_id: UUID) -> list[DocumentPage]:
    await get_document(db, document_id)
    stmt = (
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    return list((await db.scalars(stmt)).all())


async def get_page_window(
    db: AsyncSession, document_id: UUID, *, start_page: int = 1, limit: int = 8
) -> tuple[Document, list[DocumentPage]]:
    document = await get_document(db, document_id)
    start_page = max(1, start_page)
    limit = max(1, min(limit, 30))
    stmt = (
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id, DocumentPage.page_number >= start_page)
        .order_by(DocumentPage.page_number)
        .limit(limit)
    )
    pages = list((await db.scalars(stmt)).all())
    return document, pages


async def find_in_document(
    db: AsyncSession, document_id: UUID, query: str, *, limit: int = 40
) -> list[dict]:
    await get_document(db, document_id)
    query = " ".join(query.split()).strip()
    if not query:
        return []
    stmt = (
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id, DocumentPage.text.ilike(f"%{query}%"))
        .order_by(DocumentPage.page_number)
        .limit(max(1, min(limit, 100)))
    )
    pages = list((await db.scalars(stmt)).all())
    out: list[dict] = []
    q_fold = query.casefold()
    for page in pages:
        text = page.text or ""
        folded = text.casefold()
        first = folded.find(q_fold)
        count = folded.count(q_fold)
        if first < 0:
            continue
        left = max(0, first - 140)
        right = min(len(text), first + len(query) + 220)
        snippet = text[left:right].strip().replace("\n", " ")
        if left > 0:
            snippet = "…" + snippet
        if right < len(text):
            snippet += "…"
        out.append({"page_number": page.page_number, "snippet": snippet, "match_count": count})
    return out


async def get_entities(
    db: AsyncSession,
    document_id: UUID,
    *,
    entity_type: EntityType | None = None,
) -> list[DocumentEntity]:
    await get_document(db, document_id)
    stmt = select(DocumentEntity).where(DocumentEntity.document_id == document_id)
    if entity_type is not None:
        stmt = stmt.where(DocumentEntity.entity_type == entity_type)
    stmt = stmt.order_by(DocumentEntity.page_number, DocumentEntity.start_char)
    return list((await db.scalars(stmt)).all())


async def get_text(db: AsyncSession, document_id: UUID) -> tuple[Document, str]:
    document = await get_document(db, document_id)
    pages = await get_pages(db, document_id)
    return document, "\n\n".join(page.text for page in pages)


async def get_suggestions(db: AsyncSession, document_id: UUID) -> DocumentSuggestionRead:
    entities = await get_entities(db, document_id)

    def values(entity_type: EntityType) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for entity in entities:
            if entity.entity_type != entity_type:
                continue
            value = entity.normalized_value or entity.raw_text
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    return DocumentSuggestionRead(
        cnr_numbers=values(EntityType.CNR_NUMBER),
        case_numbers=values(EntityType.CASE_NUMBER),
        case_titles=values(EntityType.CASE_TITLE),
        courts=values(EntityType.COURT),
        judges=values(EntityType.JUDGE),
        acts=values(EntityType.ACT),
        statute_references=values(EntityType.STATUTE_REFERENCE),
        citations=values(EntityType.CITATION),
    )


async def delete_document(db: AsyncSession, document_id: UUID) -> None:
    document = await get_document(db, document_id)
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_document_access(db, actor, document_id, required=DocumentAccessLevel.EDIT)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    storage_key = document.storage_key
    # Search index has no direct document FK because it also indexes public corpus chunks.
    # Mark materialized document chunks deleted before removing the source record.
    try:
        from app.services.search_index.service import mark_document_deleted
        await mark_document_deleted(db, document_id)
    except Exception:
        logger.exception("Search-index tombstone failed before document deletion")
    await db.delete(document)
    await db.commit()
    delete_storage_key(storage_key)
