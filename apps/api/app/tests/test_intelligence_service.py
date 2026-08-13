from uuid import uuid4

import pytest

pytest.importorskip("aiosqlite")
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import *  # noqa: F401,F403 - register every ORM model for metadata
from app.models.document import Document, DocumentLanguage, ExtractionMethod, ProcessingStatus
from app.models.document_page import DocumentPage
from app.models.intelligence import ContradictionSeverity, StatementKind
from app.models.matter import Matter
from app.services.intelligence.service import (
    get_evidence_matrix,
    list_contradictions,
    list_statements,
    list_timeline,
    rebuild_matter_intelligence,
)


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def add_document(db: AsyncSession, matter_id, filename: str, text: str):
    document = Document(
        id=uuid4(),
        matter_id=matter_id,
        filename=filename,
        display_name=filename,
        file_extension=".txt",
        mime_type="text/plain",
        size_bytes=len(text.encode()),
        sha256=uuid4().hex + uuid4().hex,
        page_count=1,
        text_char_count=len(text),
        detected_language=DocumentLanguage.ENGLISH,
        extraction_method=ExtractionMethod.TEXT,
        is_scanned=False,
        ocr_used=False,
        processing_status=ProcessingStatus.READY,
    )
    db.add(document)
    await db.flush()
    db.add(
        DocumentPage(
            document_id=document.id,
            page_number=1,
            text=text,
            char_count=len(text),
            detected_language=DocumentLanguage.ENGLISH,
            extraction_method=ExtractionMethod.TEXT,
            is_scanned=False,
        )
    )
    await db.commit()
    return document


@pytest.mark.asyncio
async def test_rebuild_detects_single_value_date_contradiction(db: AsyncSession):
    matter = Matter(title="ABC v XYZ")
    db.add(matter)
    await db.commit()
    await db.refresh(matter)

    await add_document(
        db,
        matter.id,
        "petition.txt",
        "The parties executed the agreement on 12 March 2025. The petitioner submits that payment was made.",
    )
    await add_document(
        db,
        matter.id,
        "affidavit.txt",
        "The agreement was executed on 15 March 2025. The respondent denies that payment was made.",
    )

    summary = await rebuild_matter_intelligence(db, matter.id)
    contradictions = await list_contradictions(db, matter.id)
    timeline = await list_timeline(db, matter.id)
    statements = await list_statements(db, matter.id)
    evidence = await get_evidence_matrix(db, matter.id)

    assert summary.contradictions == 1
    assert len(contradictions) == 1
    assert contradictions[0].fact_key == "agreement_execution_date"
    assert contradictions[0].severity == ContradictionSeverity.HIGH
    assert {value.value for value in contradictions[0].values_json} == {
        "2025-03-12",
        "2025-03-15",
    }
    assert len(timeline) == 2
    assert {statement.kind for statement in statements} == {StatementKind.CLAIM, StatementKind.DENIAL}
    assert len(evidence.facts) >= 2
    assert any(item.contradiction_id is not None for item in evidence.facts)


@pytest.mark.asyncio
async def test_different_hearing_dates_are_not_flagged_as_contradiction(db: AsyncSession):
    matter = Matter(title="Hearing matter")
    db.add(matter)
    await db.commit()
    await db.refresh(matter)

    await add_document(
        db,
        matter.id,
        "orders.txt",
        "The matter was listed for hearing on 12 March 2025.\nThe next hearing was fixed on 20 April 2025.",
    )

    summary = await rebuild_matter_intelligence(db, matter.id)
    assert summary.timeline_events == 2
    assert summary.contradictions == 0
