from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.legal_corpus import (
    CitationResolutionStatus,
    Judgment,
    JudgmentCitation,
    JudgmentParagraph,
    LegalSource,
    Statute,
    StatuteSection,
)
from app.schemas.research import (
    CorpusSearchRequest,
    CorpusSearchResponse,
    CorpusStatsRead,
    SearchResultRead,
    SearchScope,
)
from app.services.research.ranking import (
    authority_score,
    bm25_scores,
    combine_scores,
    expand_query,
    language_match_score,
    make_snippet,
)

# Ranking still happens in Python, so the database must narrow the candidate set
# first. Without a text predicate this query returned an arbitrary slice of the
# corpus — fine against a handful of seeded sections, silently wrong against a
# real one. The cap is a backstop against a pathologically common term, not the
# primary filter.
CANDIDATE_CAP = 5000


def _restrict_to_query_terms(stmt, terms: list[str], columns: tuple):
    """Keep only rows where some searchable column contains one of the terms.

    ILIKE keeps this portable across SQLite (development) and PostgreSQL
    (production); the migration adds trigram indexes so PostgreSQL can serve
    these predicates from an index rather than a sequential scan.
    """
    clauses = [
        column.ilike(f"%{term}%")
        for term in terms
        if term
        for column in columns
    ]
    return stmt.where(or_(*clauses)) if clauses else stmt


async def corpus_stats(db: AsyncSession) -> CorpusStatsRead:
    async def count(model) -> int:
        return int(await db.scalar(select(func.count()).select_from(model)) or 0)

    resolved = int(
        await db.scalar(
            select(func.count()).select_from(JudgmentCitation).where(
                JudgmentCitation.status == CitationResolutionStatus.RESOLVED
            )
        ) or 0
    )
    return CorpusStatsRead(
        sources=await count(LegalSource),
        statutes=await count(Statute),
        statute_sections=await count(StatuteSection),
        judgments=await count(Judgment),
        judgment_paragraphs=await count(JudgmentParagraph),
        citations=await count(JudgmentCitation),
        resolved_citations=resolved,
    )


async def search_corpus(db: AsyncSession, payload: CorpusSearchRequest) -> CorpusSearchResponse:
    normalized_query, expanded_terms = expand_query(payload.query)
    if not expanded_terms:
        expanded_terms = [normalized_query]

    candidates: list[dict] = []

    if payload.scope in {SearchScope.ALL, SearchScope.STATUTES}:
        stmt = (
            select(StatuteSection, Statute, LegalSource)
            .join(Statute, StatuteSection.statute_id == Statute.id)
            .join(LegalSource, Statute.source_id == LegalSource.id)
            .where(Statute.is_active.is_(True), LegalSource.enabled.is_(True))
        )
        if payload.jurisdiction:
            stmt = stmt.where(Statute.jurisdiction.ilike(f"%{payload.jurisdiction}%"))
        if payload.act:
            stmt = stmt.where(or_(Statute.title_en.ilike(f"%{payload.act}%"), Statute.short_title.ilike(f"%{payload.act}%")))
        if payload.section:
            stmt = stmt.where(StatuteSection.section_number.ilike(f"%{payload.section}%"))
        if payload.as_of_date:
            stmt = stmt.where(
                or_(StatuteSection.effective_from.is_(None), StatuteSection.effective_from <= payload.as_of_date),
                or_(StatuteSection.effective_to.is_(None), StatuteSection.effective_to >= payload.as_of_date),
            )
        else:
            # Normal research defaults to versions not known to have expired. Historical
            # legal research can set as_of_date explicitly.
            stmt = stmt.where(StatuteSection.effective_to.is_(None))
        stmt = _restrict_to_query_terms(
            stmt,
            expanded_terms,
            (StatuteSection.normalized_text, StatuteSection.heading_en, StatuteSection.heading_hi),
        )
        rows = (await db.execute(stmt.limit(CANDIDATE_CAP))).all()
        for section, statute, source in rows:
            text = " ".join(filter(None, [
                statute.title_en,
                statute.title_hi,
                section.provision_type,
                section.section_number,
                section.heading_en,
                section.heading_hi,
                section.text_en,
                section.text_hi,
                section.normalized_text,
            ]))
            candidates.append({
                "kind": "statute",
                "obj": section,
                "parent": statute,
                "source": source,
                "text": text,
                "authority": 0.92,
            })

    if payload.scope in {SearchScope.ALL, SearchScope.JUDGMENTS}:
        stmt = (
            select(JudgmentParagraph, Judgment, LegalSource)
            .join(Judgment, JudgmentParagraph.judgment_id == Judgment.id)
            .join(LegalSource, Judgment.source_id == LegalSource.id)
            .where(LegalSource.enabled.is_(True))
        )
        if payload.jurisdiction:
            stmt = stmt.where(Judgment.jurisdiction.ilike(f"%{payload.jurisdiction}%"))
        if payload.court_level:
            stmt = stmt.where(Judgment.court_level == payload.court_level)
        if payload.court_name:
            stmt = stmt.where(Judgment.court_name.ilike(f"%{payload.court_name}%"))
        if payload.language:
            stmt = stmt.where(JudgmentParagraph.language == payload.language)
        if payload.date_from:
            stmt = stmt.where(Judgment.decision_date >= payload.date_from)
        if payload.date_to:
            stmt = stmt.where(Judgment.decision_date <= payload.date_to)
        stmt = _restrict_to_query_terms(
            stmt,
            expanded_terms,
            (JudgmentParagraph.normalized_text, Judgment.case_title, Judgment.neutral_citation),
        )
        rows = (await db.execute(stmt.limit(CANDIDATE_CAP))).all()
        for paragraph, judgment, source in rows:
            searchable_metadata = " ".join([
                *(str(x) for x in judgment.acts_json),
                *(str(x) for x in judgment.sections_json),
                judgment.full_text,
            ]).casefold()
            if payload.act and payload.act.casefold() not in searchable_metadata:
                continue
            if payload.section and payload.section.casefold() not in searchable_metadata:
                continue
            text = " ".join(filter(None, [
                judgment.case_title,
                judgment.case_number,
                judgment.neutral_citation,
                paragraph.text,
                paragraph.normalized_text,
                " ".join(str(x) for x in judgment.acts_json),
                " ".join(str(x) for x in judgment.sections_json),
            ]))
            candidates.append({
                "kind": "judgment",
                "obj": paragraph,
                "parent": judgment,
                "source": source,
                "text": text,
                "authority": authority_score(judgment.court_level, bench_strength=judgment.bench_strength),
            })

    lexical_scores = bm25_scores(expanded_terms, [candidate["text"] for candidate in candidates])
    results: list[SearchResultRead] = []
    for candidate, lexical in zip(candidates, lexical_scores, strict=True):
        if lexical <= 0:
            continue
        language = language_match_score(payload.query, candidate["text"])
        kind = candidate["kind"]
        obj = candidate["obj"]
        parent = candidate["parent"]
        source = candidate["source"]
        exact_reference = False
        if payload.section:
            exact_reference = payload.section.casefold() in candidate["text"].casefold()
        final = combine_scores(
            lexical=lexical,
            authority=candidate["authority"],
            language=language,
            exact_reference=exact_reference,
        )
        if kind == "statute":
            display_text = obj.text_en or obj.text_hi or obj.normalized_text
            results.append(SearchResultRead(
                id=obj.id,
                result_type="statute_section",
                title=f"{parent.title_en} — {obj.provision_type.title()} {obj.section_number}",
                subtitle=obj.heading_en or obj.heading_hi,
                snippet=make_snippet(display_text, expanded_terms),
                score=round(final, 4),
                authority_score=round(candidate["authority"], 4),
                lexical_score=round(lexical, 4),
                language_score=round(language, 4),
                source_name=source.name,
                source_url=obj.source_url or parent.source_url,
                act_title=parent.title_en,
                section_number=obj.section_number,
                metadata={"statute_id": str(parent.id), "official": source.official},
            ))
        else:
            results.append(SearchResultRead(
                id=obj.id,
                result_type="judgment_paragraph",
                title=parent.case_title,
                subtitle=parent.neutral_citation or parent.case_number,
                snippet=make_snippet(obj.text, expanded_terms),
                score=round(final, 4),
                authority_score=round(candidate["authority"], 4),
                lexical_score=round(lexical, 4),
                language_score=round(language, 4),
                source_name=source.name,
                source_url=parent.source_url,
                court_level=parent.court_level,
                court_name=parent.court_name,
                decision_date=parent.decision_date,
                paragraph_number=obj.paragraph_number,
                metadata={
                    "judgment_id": str(parent.id),
                    "case_number": parent.case_number,
                    "official": source.official,
                    "bench_strength": parent.bench_strength,
                },
            ))

    results.sort(key=lambda item: (item.score, item.authority_score), reverse=True)
    limited = results[: payload.limit]
    return CorpusSearchResponse(
        query=payload.query,
        normalized_query=normalized_query,
        expanded_terms=expanded_terms,
        total=len(results),
        results=limited,
    )


async def get_statute(db: AsyncSession, statute_id: UUID) -> Statute:
    statute = await db.scalar(
        select(Statute).where(Statute.id == statute_id).options(selectinload(Statute.sections))
    )
    if not statute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statute not found")
    return statute


async def get_section(db: AsyncSession, section_id: UUID) -> StatuteSection:
    section = await db.get(StatuteSection, section_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statute section not found")
    return section


async def get_judgment(db: AsyncSession, judgment_id: UUID) -> Judgment:
    judgment = await db.scalar(
        select(Judgment).where(Judgment.id == judgment_id).options(selectinload(Judgment.paragraphs))
    )
    if not judgment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Judgment not found")
    return judgment


async def list_judgment_citations(db: AsyncSession, judgment_id: UUID) -> list[JudgmentCitation]:
    return list((await db.scalars(
        select(JudgmentCitation)
        .where(JudgmentCitation.citing_judgment_id == judgment_id)
        .order_by(JudgmentCitation.created_at)
    )).all())


async def verify_citation(db: AsyncSession, raw: str) -> dict:
    from app.services.research.citations import normalize_citation, parse_citations

    parsed = parse_citations(raw)
    if not parsed:
        return {
            "raw": raw,
            "normalized": None,
            "parsed_reporter": None,
            "status": "unrecognized",
            "matches": [],
        }

    target = parsed[0]
    normalized = normalize_citation(target.raw)
    judgments = list((await db.scalars(select(Judgment))).all())
    matches = []
    for judgment in judgments:
        candidates = [judgment.neutral_citation, *judgment.reported_citations_json]
        normalized_candidates = {
            normalize_citation(candidate) for candidate in candidates if candidate
        }
        if normalized in normalized_candidates:
            matches.append({
                "judgment_id": judgment.id,
                "case_title": judgment.case_title,
                "court_name": judgment.court_name,
                "decision_date": judgment.decision_date,
                "neutral_citation": judgment.neutral_citation,
                "reported_citations": list(judgment.reported_citations_json),
                "source_url": judgment.source_url,
            })
    return {
        "raw": raw,
        "normalized": normalized,
        "parsed_reporter": target.reporter,
        "status": "resolved" if len(matches) == 1 else "ambiguous" if len(matches) > 1 else "unresolved",
        "matches": matches,
    }


async def cited_by(db: AsyncSession, judgment_id: UUID) -> list[dict]:
    judgment = await db.get(Judgment, judgment_id)
    if not judgment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Judgment not found")

    rows = (await db.execute(
        select(JudgmentCitation, Judgment)
        .join(Judgment, JudgmentCitation.citing_judgment_id == Judgment.id)
        .where(JudgmentCitation.cited_judgment_id == judgment_id)
        .order_by(Judgment.decision_date.desc())
    )).all()
    return [
        {
            "citation_id": citation.id,
            "citing_judgment_id": citing.id,
            "citing_case_title": citing.case_title,
            "citing_court_name": citing.court_name,
            "citing_decision_date": citing.decision_date,
            "paragraph_id": citation.paragraph_id,
            "raw_citation": citation.raw_citation,
            "normalized_citation": citation.normalized_citation,
            "source_url": citing.source_url,
        }
        for citation, citing in rows
    ]


async def list_statutes(
    db: AsyncSession,
    *,
    search: str | None = None,
    jurisdiction: str | None = None,
    state: str | None = None,
    year: int | None = None,
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Statute], int]:
    """Browse the Acts shelf.

    Filtering happens in SQL rather than in Python: the corpus is meant to hold
    every bare act a practice needs, and pulling that into memory to filter it
    would stop working exactly when the shelf becomes useful.
    """
    conditions = []
    if active_only:
        conditions.append(Statute.is_active.is_(True))
    if jurisdiction:
        conditions.append(Statute.jurisdiction == jurisdiction)
    if state:
        conditions.append(Statute.state == state)
    if year:
        conditions.append(Statute.act_year == year)
    if search:
        # Match the title in either language, the short title, or the act
        # number — a lawyer looks up "138" and "एन.आई." as readily as a name.
        needle = f"%{search.strip()}%"
        conditions.append(
            or_(
                Statute.title_en.ilike(needle),
                Statute.title_hi.ilike(needle),
                Statute.short_title.ilike(needle),
                Statute.act_number.ilike(needle),
            )
        )

    total = await db.scalar(
        select(func.count()).select_from(Statute).where(*conditions)
    )
    rows = await db.scalars(
        select(Statute)
        .where(*conditions)
        .order_by(Statute.act_year.desc().nullslast(), Statute.title_en)
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all()), int(total or 0)


async def statute_shelf(db: AsyncSession) -> dict:
    """Counts for the browse filters, so the interface shows what exists."""
    jurisdictions = await db.execute(
        select(Statute.jurisdiction, func.count())
        .where(Statute.is_active.is_(True))
        .group_by(Statute.jurisdiction)
        .order_by(func.count().desc())
    )
    states = await db.execute(
        select(Statute.state, func.count())
        .where(Statute.is_active.is_(True), Statute.state.is_not(None))
        .group_by(Statute.state)
        .order_by(func.count().desc())
    )
    total = await db.scalar(
        select(func.count()).select_from(Statute).where(Statute.is_active.is_(True))
    )
    return {
        "total_acts": int(total or 0),
        "jurisdictions": [
            {"name": name, "count": count} for name, count in jurisdictions.all()
        ],
        "states": [{"name": name, "count": count} for name, count in states.all()],
    }


async def search_sections(
    db: AsyncSession,
    statute_id: UUID,
    *,
    query: str,
    limit: int = 40,
) -> list[StatuteSection]:
    """Find a provision inside one act by number or wording."""
    needle = f"%{query.strip()}%"
    rows = await db.scalars(
        select(StatuteSection)
        .where(
            StatuteSection.statute_id == statute_id,
            or_(
                StatuteSection.section_number.ilike(needle),
                StatuteSection.heading_en.ilike(needle),
                StatuteSection.heading_hi.ilike(needle),
                StatuteSection.normalized_text.ilike(needle),
            ),
        )
        .order_by(StatuteSection.sort_order)
        .limit(limit)
    )
    return list(rows.all())
