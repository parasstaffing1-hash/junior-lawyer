from __future__ import annotations

from dataclasses import dataclass, field, replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AISourceType
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.legal_corpus import JudgmentParagraph, StatuteSection
from app.models.intelligence import (
    ContradictionStatus,
    FactStatus,
    MatterContradiction,
    MatterFact,
    MatterStatement,
    TimelineEvent,
)
from app.models.matter import Matter
from app.schemas.research import CorpusSearchRequest
from app.services.ai.prompting import estimate_tokens
from app.services.research.ranking import bm25_scores, expand_query
from app.services.research.service import search_corpus


@dataclass(slots=True)
class RetrievedSource:
    ordinal: int
    source_key: str
    source_type: AISourceType
    source_record_id: str
    title: str
    locator: str | None
    text: str
    source_url: str | None = None
    official: bool = False
    verified: bool = False
    relevance_score: float = 0.0
    metadata_json: dict = field(default_factory=dict)


async def retrieve_sources(
    db: AsyncSession,
    *,
    query: str,
    matter_id: UUID | None,
    include_corpus: bool,
    max_sources: int,
    max_input_tokens: int,
) -> tuple[list[RetrievedSource], dict]:
    candidates: list[RetrievedSource] = []
    if matter_id is not None:
        matter = await db.get(Matter, matter_id)
        if not matter:
            raise ValueError("Matter not found")
        candidates.extend(await _matter_candidates(db, matter_id))

    if include_corpus:
        try:
            response = await search_corpus(db, CorpusSearchRequest(query=query, limit=min(max_sources, 12)))
        except Exception:
            response = None
        if response:
            for result in response.results:
                source_type = (
                    AISourceType.STATUTE_SECTION
                    if result.result_type == "statute_section"
                    else AISourceType.JUDGMENT_PARAGRAPH
                )
                locator = None
                source_text = result.snippet
                if result.result_type == "statute_section":
                    locator = f"Section {result.section_number}" if result.section_number else None
                    section = await db.get(StatuteSection, result.id)
                    if section:
                        source_text = section.text_en or section.text_hi or section.normalized_text or result.snippet
                else:
                    if result.paragraph_number:
                        locator = f"Paragraph {result.paragraph_number}"
                    paragraph = await db.get(JudgmentParagraph, result.id)
                    if paragraph:
                        source_text = paragraph.text
                candidates.append(
                    RetrievedSource(
                        ordinal=0,
                        source_key="",
                        source_type=source_type,
                        source_record_id=str(result.id),
                        title=result.title,
                        locator=locator,
                        text=source_text,
                        source_url=result.source_url,
                        official=bool(result.metadata.get("official")),
                        verified=bool(result.metadata.get("official")),
                        relevance_score=float(result.score),
                        metadata_json={
                            "authority_score": result.authority_score,
                            "court_name": result.court_name,
                            "court_level": result.court_level.value if result.court_level else None,
                            "decision_date": result.decision_date.isoformat() if result.decision_date else None,
                            "act_title": result.act_title,
                            "section_number": result.section_number,
                            **result.metadata,
                        },
                    )
                )

    if not candidates:
        return [], {"candidate_count": 0, "selected_count": 0, "estimated_source_tokens": 0}

    # Rank matter sources against the query. Corpus candidates already carry their own score,
    # but receive lexical scoring as a second deterministic signal.
    _, terms = expand_query(query)
    lexical = bm25_scores(terms or [query.casefold()], [c.text for c in candidates])
    rescored: list[RetrievedSource] = []
    for candidate, score in zip(candidates, lexical, strict=True):
        base = candidate.relevance_score
        combined = min(1.0, max(base, score) * 0.78 + (0.12 if candidate.verified else 0.0) + (0.10 if candidate.official else 0.0))
        rescored.append(replace(candidate, relevance_score=round(combined, 4)))
    rescored.sort(key=lambda x: (x.relevance_score, x.verified, x.official), reverse=True)

    selected: list[RetrievedSource] = []
    token_budget = max(250, max_input_tokens - 900)
    used = 0
    for candidate in rescored:
        if len(selected) >= max_sources:
            break
        text = " ".join(candidate.text.split())
        if len(text) > 1800:
            text = text[:1799].rstrip() + "…"
        candidate = replace(candidate, text=text)
        cost = estimate_tokens(text) + 35
        if used + cost > token_budget:
            remaining = token_budget - used - 35
            if remaining < 80:
                continue
            max_chars = max(220, int(remaining * 3.0))
            candidate = replace(candidate, text=text[:max_chars].rstrip() + "…")
            cost = estimate_tokens(candidate.text) + 35
        selected.append(candidate)
        used += cost

    selected = [replace(item, ordinal=i, source_key=f"S{i}") for i, item in enumerate(selected, 1)]
    return selected, {
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "estimated_source_tokens": used,
        "source_types": _count_types(selected),
    }


async def _matter_candidates(db: AsyncSession, matter_id: UUID) -> list[RetrievedSource]:
    candidates: list[RetrievedSource] = []
    documents = {doc.id: doc for doc in (await db.scalars(select(Document).where(Document.matter_id == matter_id))).all()}

    facts = (await db.scalars(
        select(MatterFact)
        .where(MatterFact.matter_id == matter_id, MatterFact.status != FactStatus.REJECTED)
        .options(selectinload(MatterFact.sources))
    )).all()
    for fact in facts:
        source = fact.sources[0] if fact.sources else None
        document = documents.get(source.document_id) if source else None
        quote = source.quote if source else ""
        text = f"{fact.label}: {fact.value_text}."
        if quote:
            text += f" Source excerpt: {quote}"
        candidates.append(RetrievedSource(
            ordinal=0, source_key="", source_type=AISourceType.MATTER_FACT,
            source_record_id=str(fact.id), title=f"Matter fact · {fact.label}",
            locator=_doc_locator(document, source.page_number if source else None), text=text,
            verified=fact.status == FactStatus.CONFIRMED,
            metadata_json={"fact_key": fact.fact_key, "confidence": fact.confidence, "fact_status": fact.status.value},
        ))

    events = (await db.scalars(
        select(TimelineEvent).where(TimelineEvent.matter_id == matter_id).options(selectinload(TimelineEvent.sources))
    )).all()
    for event in events:
        source = event.sources[0] if event.sources else None
        document = documents.get(source.document_id) if source else None
        candidates.append(RetrievedSource(
            ordinal=0, source_key="", source_type=AISourceType.TIMELINE_EVENT,
            source_record_id=str(event.id), title=f"Timeline · {event.title}",
            locator=_doc_locator(document, source.page_number if source else None),
            text=f"{event.event_date.isoformat()} — {event.description}", verified=False,
            metadata_json={"event_type": event.event_type, "confidence": event.confidence},
        ))

    statements = (await db.scalars(select(MatterStatement).where(MatterStatement.matter_id == matter_id))).all()
    for statement in statements:
        document = documents.get(statement.document_id)
        candidates.append(RetrievedSource(
            ordinal=0, source_key="", source_type=AISourceType.STATEMENT,
            source_record_id=str(statement.id), title=f"{statement.kind.value.title()} · {statement.speaker_role or 'unspecified speaker'}",
            locator=_doc_locator(document, statement.page_number), text=statement.raw_text, verified=False,
            metadata_json={"statement_kind": statement.kind.value, "confidence": statement.confidence},
        ))

    contradictions = (await db.scalars(
        select(MatterContradiction).where(
            MatterContradiction.matter_id == matter_id,
            MatterContradiction.status == ContradictionStatus.OPEN,
        )
    )).all()
    for conflict in contradictions:
        values = "; ".join(str(v.get("display") or v.get("value")) for v in conflict.values_json)
        candidates.append(RetrievedSource(
            ordinal=0, source_key="", source_type=AISourceType.CONTRADICTION,
            source_record_id=str(conflict.id), title=f"Open contradiction · {conflict.label}", locator=None,
            text=f"{conflict.explanation} Conflicting values: {values}", verified=False,
            relevance_score=0.35,
            metadata_json={"severity": conflict.severity.value, "status": conflict.status.value},
        ))

    pages = (await db.execute(
        select(DocumentPage, Document)
        .join(Document, DocumentPage.document_id == Document.id)
        .where(Document.matter_id == matter_id, DocumentPage.text != "")
        .limit(1600)
    )).all()
    for page, document in pages:
        candidates.append(RetrievedSource(
            ordinal=0, source_key="", source_type=AISourceType.DOCUMENT_PAGE,
            source_record_id=str(page.id), title=document.display_name or document.filename,
            locator=f"Page {page.page_number}", text=page.text, verified=False,
            metadata_json={"document_id": str(document.id), "language": page.detected_language.value, "extraction_method": page.extraction_method.value},
        ))
    return candidates


def _doc_locator(document: Document | None, page_number: int | None) -> str | None:
    if not document and page_number is None:
        return None
    name = (document.display_name or document.filename) if document else "Document"
    return f"{name} · p.{page_number}" if page_number is not None else name


def _count_types(sources: list[RetrievedSource]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources:
        counts[source.source_type.value] = counts.get(source.source_type.value, 0) + 1
    return counts
