from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.legal_corpus import LegalSource
from app.schemas.research import (
    CitationGraphEdgeRead,
    CitationRead,
    CitationVerifyRequest,
    CitationVerifyResponse,
    CorpusSearchRequest,
    CorpusSearchResponse,
    CorpusStatsRead,
    JudgmentImportRequest,
    JudgmentParagraphRead,
    JudgmentRead,
    SourceRead,
    StatuteImportRequest,
    StatuteRead,
    StatuteSectionRead,
)
from app.services.research import importer, service

router = APIRouter(prefix="/research", tags=["legal-research"])


@router.post("/search", response_model=CorpusSearchResponse)
async def search_corpus(
    payload: CorpusSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> CorpusSearchResponse:
    return await service.search_corpus(db, payload)


@router.get("/stats", response_model=CorpusStatsRead)
async def corpus_stats(db: AsyncSession = Depends(get_db)) -> CorpusStatsRead:
    return await service.corpus_stats(db)


@router.post("/sources/seed", response_model=list[SourceRead])
async def seed_sources(db: AsyncSession = Depends(get_db)) -> list[SourceRead]:
    return await importer.seed_official_sources(db)


@router.get("/sources", response_model=list[SourceRead])
async def list_sources(db: AsyncSession = Depends(get_db)) -> list[SourceRead]:
    return list((await db.scalars(select(LegalSource).order_by(LegalSource.name))).all())


@router.post("/corpus/statutes/import", response_model=StatuteRead)
async def import_statute(
    payload: StatuteImportRequest,
    db: AsyncSession = Depends(get_db),
) -> StatuteRead:
    return await importer.import_statute(db, payload)


@router.get("/statutes/{statute_id}", response_model=StatuteRead)
async def get_statute(statute_id: UUID, db: AsyncSession = Depends(get_db)) -> StatuteRead:
    return await service.get_statute(db, statute_id)


@router.get("/statutes/{statute_id}/sections", response_model=list[StatuteSectionRead])
async def get_statute_sections(
    statute_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[StatuteSectionRead]:
    statute = await service.get_statute(db, statute_id)
    return statute.sections


@router.get("/sections/{section_id}", response_model=StatuteSectionRead)
async def get_section(section_id: UUID, db: AsyncSession = Depends(get_db)) -> StatuteSectionRead:
    return await service.get_section(db, section_id)


@router.post("/corpus/judgments/import", response_model=JudgmentRead)
async def import_judgment(
    payload: JudgmentImportRequest,
    db: AsyncSession = Depends(get_db),
) -> JudgmentRead:
    return await importer.import_judgment(db, payload)


@router.get("/judgments/{judgment_id}", response_model=JudgmentRead)
async def get_judgment(judgment_id: UUID, db: AsyncSession = Depends(get_db)) -> JudgmentRead:
    return await service.get_judgment(db, judgment_id)


@router.get("/judgments/{judgment_id}/paragraphs", response_model=list[JudgmentParagraphRead])
async def get_judgment_paragraphs(
    judgment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[JudgmentParagraphRead]:
    judgment = await service.get_judgment(db, judgment_id)
    return judgment.paragraphs


@router.get("/judgments/{judgment_id}/citations", response_model=list[CitationRead])
async def get_judgment_citations(
    judgment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[CitationRead]:
    return await service.list_judgment_citations(db, judgment_id)


@router.post("/citations/resolve")
async def resolve_citations(
    judgment_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    return await importer.resolve_citations(db, judgment_id)


@router.post("/citations/verify", response_model=CitationVerifyResponse)
async def verify_citation(
    payload: CitationVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> CitationVerifyResponse:
    return await service.verify_citation(db, payload.citation)


@router.get(
    "/judgments/{judgment_id}/cited-by",
    response_model=list[CitationGraphEdgeRead],
)
async def judgment_cited_by(
    judgment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[CitationGraphEdgeRead]:
    return await service.cited_by(db, judgment_id)
