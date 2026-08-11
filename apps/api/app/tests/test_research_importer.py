from datetime import date

import pytest

aiosqlite = pytest.importorskip("aiosqlite", reason="aiosqlite is declared by the project but absent in this sandbox")
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.legal_corpus import CitationResolutionStatus, CourtLevel, JudgmentCitation
from app.schemas.research import (
    CorpusSearchRequest,
    JudgmentImportParagraph,
    JudgmentImportRequest,
    StatuteImportRequest,
    StatuteImportSection,
)
from app.services.research import importer, service


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_import_search_and_citation_resolution(db: AsyncSession) -> None:
    await importer.seed_official_sources(db)

    act = await importer.import_statute(
        db,
        StatuteImportRequest(
            external_id="demo-ni-act",
            title_en="Negotiable Instruments Act, 1881",
            act_year=1881,
            source_url="https://www.indiacode.nic.in/demo",
            sections=[
                StatuteImportSection(
                    section_number="138",
                    heading_en="Dishonour of cheque for insufficiency of funds",
                    text_en="Where any cheque is returned unpaid, the drawer may be liable subject to notice requirements.",
                    text_hi="चेक अनादर होने पर नोटिस की आवश्यकताओं के अधीन दायित्व उत्पन्न हो सकता है।",
                )
            ],
        ),
    )
    assert len(act.sections) == 1

    cited = await importer.import_judgment(
        db,
        JudgmentImportRequest(
            source_code="supreme_court",
            external_id="sc-2024-100",
            case_title="Alpha v. Beta",
            case_number="C.A. 100/2024",
            neutral_citation="2024 INSC 100",
            reported_citations=["(2024) 5 SCC 123"],
            court_name="Supreme Court of India",
            court_level=CourtLevel.SUPREME_COURT,
            decision_date=date(2024, 4, 5),
            judges=["Justice A", "Justice B"],
            acts=["Negotiable Instruments Act, 1881"],
            sections=["138"],
            paragraphs=[
                JudgmentImportParagraph(
                    paragraph_number="12",
                    text="Section 138 requires proof of statutory notice after dishonour of cheque.",
                )
            ],
        ),
    )

    citing = await importer.import_judgment(
        db,
        JudgmentImportRequest(
            source_code="supreme_court",
            external_id="sc-2025-200",
            case_title="Gamma v. Delta",
            neutral_citation="2025 INSC 200",
            court_name="Supreme Court of India",
            court_level=CourtLevel.SUPREME_COURT,
            decision_date=date(2025, 3, 2),
            paragraphs=[
                JudgmentImportParagraph(
                    paragraph_number="8",
                    text="We follow Alpha v. Beta, (2024) 5 SCC 123, on the notice requirement.",
                )
            ],
        ),
    )

    resolution = await importer.resolve_citations(db, citing.id)
    assert resolution["resolved"] == 1

    citations = await service.list_judgment_citations(db, citing.id)
    assert citations[0].status == CitationResolutionStatus.RESOLVED
    assert citations[0].cited_judgment_id == cited.id

    result = await service.search_corpus(
        db,
        CorpusSearchRequest(query="धारा 138 cheque notice", limit=10),
    )
    assert result.total >= 2
    assert any(item.result_type == "statute_section" for item in result.results)
    assert any(item.result_type == "judgment_paragraph" for item in result.results)
    assert result.results[0].score > 0
