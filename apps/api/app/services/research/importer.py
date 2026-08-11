from __future__ import annotations

import hashlib
import re
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.legal_corpus import (
    AccessMode,
    CitationResolutionStatus,
    CorpusLanguage,
    Judgment,
    JudgmentCitation,
    JudgmentParagraph,
    LegalSource,
    LegalSourceKind,
    Statute,
    StatuteSection,
)
from app.schemas.research import JudgmentImportRequest, StatuteImportRequest
from app.services.language.normalizer import normalize_legal_text
from app.services.research.citations import normalize_citation, parse_citations


OFFICIAL_SOURCE_SEEDS = [
    {
        "code": "india_code",
        "name": "India Code",
        "kind": LegalSourceKind.INDIA_CODE,
        "base_url": "https://www.indiacode.nic.in/",
        "access_mode": AccessMode.OFFICIAL_DOWNLOAD,
        "notes": "Authoritative statute corpus. Import downloaded/approved official material; preserve source URL and hash.",
    },
    {
        "code": "ecourts_judgments",
        "name": "Judgements and Orders — eCourts",
        "kind": LegalSourceKind.ECOURTS,
        "base_url": "https://judgments.ecourts.gov.in/",
        "access_mode": AccessMode.MANUAL_IMPORT,
        "notes": "Official High Court judgment search. Do not bypass CAPTCHA or access controls; ingest permitted downloads/exports.",
    },
    {
        "code": "supreme_court",
        "name": "Supreme Court of India",
        "kind": LegalSourceKind.SUPREME_COURT,
        "base_url": "https://www.sci.gov.in/",
        "access_mode": AccessMode.MANUAL_IMPORT,
        "notes": "Official Supreme Court judgments/orders. Ingest permitted official downloads and retain source provenance.",
    },
]


def _hash_text(*parts: str | None) -> str:
    payload = "\n".join(part or "" for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _section_key(number: str, effective_from: object | None, version_label: str | None) -> str:
    clean = re.sub(r"\s+", "", number).upper()
    version = str(effective_from or version_label or "current")
    return f"section:{clean}:{version}"


async def seed_official_sources(db: AsyncSession) -> list[LegalSource]:
    results: list[LegalSource] = []
    for seed in OFFICIAL_SOURCE_SEEDS:
        existing = await db.scalar(select(LegalSource).where(LegalSource.code == seed["code"]))
        if existing:
            results.append(existing)
            continue
        source = LegalSource(
            code=seed["code"],
            name=seed["name"],
            kind=seed["kind"],
            base_url=seed["base_url"],
            jurisdiction="India",
            official=True,
            access_mode=seed["access_mode"],
            enabled=True,
            notes=seed["notes"],
            metadata_json={"seeded": True},
        )
        db.add(source)
        await db.flush()
        results.append(source)
    await db.commit()
    return results


async def _get_source(db: AsyncSession, code: str) -> LegalSource:
    source = await db.scalar(select(LegalSource).where(LegalSource.code == code))
    if source:
        return source
    await seed_official_sources(db)
    source = await db.scalar(select(LegalSource).where(LegalSource.code == code))
    if not source:
        raise ValueError(f"Unknown legal source: {code}")
    return source


async def import_statute(db: AsyncSession, payload: StatuteImportRequest) -> Statute:
    source = await _get_source(db, payload.source_code)
    statute = await db.scalar(
        select(Statute).where(
            Statute.source_id == source.id,
            Statute.external_id == payload.external_id,
        )
    )
    source_hash = _hash_text(payload.title_en, payload.source_url, str(payload.sections))

    if statute is None:
        statute = Statute(source_id=source.id, external_id=payload.external_id, title_en=payload.title_en)
        db.add(statute)
        await db.flush()

    statute.title_en = payload.title_en
    statute.title_hi = payload.title_hi
    statute.short_title = payload.short_title
    statute.act_number = payload.act_number
    statute.act_year = payload.act_year
    statute.enactment_date = payload.enactment_date
    statute.ministry = payload.ministry
    statute.department = payload.department
    statute.jurisdiction = payload.jurisdiction
    statute.state = payload.state
    statute.source_url = payload.source_url
    statute.source_hash = source_hash
    statute.metadata_json = payload.metadata

    # Sections are version-aware. We never delete other section versions during an import.
    # A caller must supply effective_from or version_label when it wants a historical
    # version to coexist with the current text; the importer does not invent legal dates.
    for position, section in enumerate(payload.sections, start=1):
        section_key = _section_key(section.section_number, section.effective_from, section.version_label)
        normalized = normalize_legal_text(" ".join(filter(None, [
            section.heading_en,
            section.heading_hi,
            section.text_en,
            section.text_hi,
        ])))
        record = await db.scalar(
            select(StatuteSection).where(
                StatuteSection.statute_id == statute.id,
                StatuteSection.section_key == section_key,
            )
        )
        if record is None:
            record = StatuteSection(
                statute_id=statute.id,
                section_key=section_key,
                section_number=section.section_number,
            )
            db.add(record)
        record.provision_type = section.provision_type
        record.heading_en = section.heading_en
        record.heading_hi = section.heading_hi
        record.text_en = section.text_en
        record.text_hi = section.text_hi
        record.normalized_text = normalized
        record.sort_order = position
        record.effective_from = section.effective_from
        record.effective_to = section.effective_to
        record.version_label = section.version_label
        record.source_url = section.source_url or payload.source_url
        record.source_hash = _hash_text(section.text_en, section.text_hi)
        record.metadata_json = section.metadata
    await db.commit()
    await db.refresh(statute, attribute_names=["sections"])
    return statute


async def import_judgment(db: AsyncSession, payload: JudgmentImportRequest) -> Judgment:
    source = await _get_source(db, payload.source_code)
    judgment = await db.scalar(
        select(Judgment).where(
            Judgment.source_id == source.id,
            Judgment.external_id == payload.external_id,
        )
    )
    if judgment is None:
        judgment = Judgment(
            source_id=source.id,
            external_id=payload.external_id,
            case_title=payload.case_title,
            court_name=payload.court_name,
            court_level=payload.court_level,
        )
        db.add(judgment)
        await db.flush()

    full_text = "\n\n".join(item.text for item in payload.paragraphs)
    judgment.case_title = payload.case_title
    judgment.case_number = payload.case_number
    judgment.neutral_citation = payload.neutral_citation
    judgment.reported_citations_json = payload.reported_citations
    judgment.court_name = payload.court_name
    judgment.court_level = payload.court_level
    judgment.jurisdiction = payload.jurisdiction
    judgment.decision_date = payload.decision_date
    judgment.judges_json = payload.judges
    judgment.bench_strength = payload.bench_strength or (len(payload.judges) or None)
    judgment.acts_json = payload.acts
    judgment.sections_json = payload.sections
    judgment.language = payload.language
    judgment.full_text = full_text
    judgment.normalized_text = normalize_legal_text(full_text)
    judgment.source_url = payload.source_url
    judgment.source_hash = _hash_text(full_text, payload.source_url)
    judgment.metadata_json = payload.metadata

    await db.execute(delete(JudgmentCitation).where(JudgmentCitation.citing_judgment_id == judgment.id))
    await db.execute(delete(JudgmentParagraph).where(JudgmentParagraph.judgment_id == judgment.id))
    await db.flush()

    paragraphs: list[JudgmentParagraph] = []
    for position, item in enumerate(payload.paragraphs, start=1):
        paragraph = JudgmentParagraph(
            judgment_id=judgment.id,
            paragraph_number=item.paragraph_number,
            position=position,
            text=item.text,
            normalized_text=normalize_legal_text(item.text),
            language=item.language,
            metadata_json=item.metadata,
        )
        db.add(paragraph)
        paragraphs.append(paragraph)
    await db.flush()

    for paragraph in paragraphs:
        for citation in parse_citations(paragraph.text):
            db.add(
                JudgmentCitation(
                    citing_judgment_id=judgment.id,
                    paragraph_id=paragraph.id,
                    raw_citation=citation.raw,
                    normalized_citation=citation.normalized,
                    status=CitationResolutionStatus.UNRESOLVED,
                    confidence=0.98,
                    metadata_json={"reporter": citation.reporter},
                )
            )
    await db.commit()
    await db.refresh(judgment, attribute_names=["paragraphs", "outgoing_citations"])
    return judgment


async def resolve_citations(db: AsyncSession, judgment_id: UUID | None = None) -> dict[str, int]:
    query = select(JudgmentCitation)
    if judgment_id:
        query = query.where(JudgmentCitation.citing_judgment_id == judgment_id)
    citations = list((await db.scalars(query)).all())
    judgments = list((await db.scalars(select(Judgment))).all())

    lookup: dict[str, list[Judgment]] = {}
    for judgment in judgments:
        candidates = [judgment.neutral_citation, *judgment.reported_citations_json]
        for candidate in candidates:
            if candidate:
                lookup.setdefault(normalize_citation(candidate), []).append(judgment)

    resolved = ambiguous = unresolved = 0
    for citation in citations:
        matches = lookup.get(citation.normalized_citation, [])
        if len(matches) == 1:
            citation.cited_judgment_id = matches[0].id
            citation.status = CitationResolutionStatus.RESOLVED
            resolved += 1
        elif len(matches) > 1:
            citation.cited_judgment_id = None
            citation.status = CitationResolutionStatus.AMBIGUOUS
            ambiguous += 1
        else:
            citation.cited_judgment_id = None
            citation.status = CitationResolutionStatus.UNRESOLVED
            unresolved += 1
    await db.commit()
    return {"resolved": resolved, "ambiguous": ambiguous, "unresolved": unresolved}
