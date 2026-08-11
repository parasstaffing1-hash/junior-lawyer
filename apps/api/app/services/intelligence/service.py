from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, ProcessingStatus
from app.models.document_page import DocumentPage
from app.models.intelligence import (
    ContradictionSeverity,
    ContradictionStatus,
    FactSource,
    FactStatus,
    MatterContradiction,
    MatterFact,
    MatterStatement,
    ReviewItem,
    ReviewItemType,
    ReviewPriority,
    ReviewStatus,
    SourceRelation,
    StatementKind,
    TimelineEvent,
    TimelineEventSource,
)
from app.models.matter import Matter
from app.models.security import MatterAccessLevel
from app.services.security.context import get_current_actor
from app.services.security.permissions import decide_matter_access
from app.schemas.intelligence import (
    ContradictionRead,
    EvidenceFactRead,
    EvidenceMatrixRead,
    FactRead,
    IntelligenceSummaryRead,
    RebuildResultRead,
    ReviewItemRead,
    SourceRead,
    StatementRead,
    TimelineEventRead,
    TimelineSourceRead,
)
from app.services.intelligence.extractor import extract_intelligence


CONFLICT_FACT_KEYS = {
    "agreement_execution_date",
    "fir_registration_date",
    "arrest_date",
    "termination_date",
    "possession_date",
    "registration_date",
    "contract_amount",
}

SEVERITY_BY_FACT_KEY = {
    "agreement_execution_date": ContradictionSeverity.HIGH,
    "fir_registration_date": ContradictionSeverity.HIGH,
    "arrest_date": ContradictionSeverity.HIGH,
    "termination_date": ContradictionSeverity.HIGH,
    "contract_amount": ContradictionSeverity.HIGH,
    "possession_date": ContradictionSeverity.MEDIUM,
    "registration_date": ContradictionSeverity.MEDIUM,
}


def _contradiction_label(fact_key: str, fallback: str) -> str:
    labels = {
        "agreement_execution_date": "Agreement execution date",
        "fir_registration_date": "FIR registration date",
        "arrest_date": "Arrest date",
        "termination_date": "Termination date",
        "possession_date": "Possession date",
        "registration_date": "Registration date",
        "contract_amount": "Contract / consideration amount",
    }
    return labels.get(fact_key, fallback)


async def _ensure_matter(
    db: AsyncSession,
    matter_id: UUID,
    *,
    required: MatterAccessLevel = MatterAccessLevel.VIEW,
) -> Matter:
    matter = await db.get(Matter, matter_id)
    if matter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    actor = get_current_actor()
    if actor is not None:
        decision = await decide_matter_access(db, actor, matter_id, required=required)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    return matter


async def _clear_generated_intelligence(db: AsyncSession, matter_id: UUID) -> None:
    # Review items and contradictions reference generated rows by string IDs, so remove them first.
    await db.execute(delete(ReviewItem).where(ReviewItem.matter_id == matter_id))
    await db.execute(delete(MatterContradiction).where(MatterContradiction.matter_id == matter_id))

    event_ids = select(TimelineEvent.id).where(TimelineEvent.matter_id == matter_id)
    await db.execute(delete(TimelineEventSource).where(TimelineEventSource.event_id.in_(event_ids)))
    await db.execute(delete(TimelineEvent).where(TimelineEvent.matter_id == matter_id))

    fact_ids = select(MatterFact.id).where(MatterFact.matter_id == matter_id)
    await db.execute(delete(FactSource).where(FactSource.fact_id.in_(fact_ids)))
    await db.execute(delete(MatterFact).where(MatterFact.matter_id == matter_id))
    await db.execute(delete(MatterStatement).where(MatterStatement.matter_id == matter_id))
    await db.flush()


async def rebuild_matter_intelligence(db: AsyncSession, matter_id: UUID) -> RebuildResultRead:
    await _ensure_matter(db, matter_id, required=MatterAccessLevel.WORK)

    # Preserve human decisions for facts/contradictions that deterministically regenerate to the same key.
    prior_fact_status_rows = await db.execute(
        select(MatterFact.fact_key, MatterFact.normalized_value, MatterFact.status)
        .where(MatterFact.matter_id == matter_id)
    )
    prior_fact_status = {
        (row.fact_key, row.normalized_value): row.status
        for row in prior_fact_status_rows
        if row.status != FactStatus.AUTO
    }
    prior_contradiction_rows = await db.execute(
        select(MatterContradiction.contradiction_key, MatterContradiction.status)
        .where(MatterContradiction.matter_id == matter_id)
    )
    prior_contradiction_status = {
        row.contradiction_key: row.status
        for row in prior_contradiction_rows
        if row.status != ContradictionStatus.OPEN
    }

    await _clear_generated_intelligence(db, matter_id)

    stmt = (
        select(DocumentPage, Document)
        .join(Document, Document.id == DocumentPage.document_id)
        .where(
            Document.matter_id == matter_id,
            Document.processing_status == ProcessingStatus.READY,
        )
        .order_by(Document.created_at, DocumentPage.page_number)
    )
    page_rows = list((await db.execute(stmt)).all())

    fact_map: dict[tuple[str, str], MatterFact] = {}
    event_map: dict[str, TimelineEvent] = {}
    statement_seen: set[tuple[UUID, int | None, StatementKind, str]] = set()
    source_documents: set[UUID] = set()
    source_pages: set[UUID] = set()

    for page, document in page_rows:
        source_documents.add(document.id)
        source_pages.add(page.id)
        extraction = extract_intelligence(page.text)

        for candidate in extraction.facts:
            key = (candidate.fact_key, candidate.normalized_value)
            fact = fact_map.get(key)
            if fact is None:
                fact = MatterFact(
                    matter_id=matter_id,
                    fact_key=candidate.fact_key,
                    fact_type=candidate.fact_type,
                    category=candidate.category,
                    label=candidate.label,
                    value_text=candidate.value_text,
                    normalized_value=candidate.normalized_value,
                    confidence=candidate.confidence,
                    status=prior_fact_status.get(key, FactStatus.AUTO),
                    metadata_json=candidate.metadata,
                )
                db.add(fact)
                await db.flush()
                fact_map[key] = fact
            else:
                fact.confidence = max(fact.confidence, candidate.confidence)

            db.add(
                FactSource(
                    fact_id=fact.id,
                    document_id=document.id,
                    page_id=page.id,
                    page_number=page.page_number,
                    relation=SourceRelation.SUPPORTS,
                    quote=candidate.quote,
                    start_char=candidate.start_char,
                    end_char=candidate.end_char,
                    confidence=candidate.confidence,
                    metadata_json={"filename": document.filename},
                )
            )

        for candidate in extraction.events:
            event = event_map.get(candidate.event_key)
            if event is None:
                event = TimelineEvent(
                    matter_id=matter_id,
                    event_key=candidate.event_key,
                    event_type=candidate.event_type,
                    event_date=candidate.event_date,
                    title=candidate.title,
                    description=candidate.description,
                    confidence=candidate.confidence,
                    metadata_json=candidate.metadata,
                )
                db.add(event)
                await db.flush()
                event_map[candidate.event_key] = event
            else:
                event.confidence = max(event.confidence, candidate.confidence)

            db.add(
                TimelineEventSource(
                    event_id=event.id,
                    document_id=document.id,
                    page_id=page.id,
                    page_number=page.page_number,
                    quote=candidate.quote,
                    start_char=candidate.start_char,
                    end_char=candidate.end_char,
                    confidence=candidate.confidence,
                )
            )

        for candidate in extraction.statements:
            statement_key = (
                document.id,
                page.page_number,
                candidate.kind,
                candidate.normalized_text,
            )
            if statement_key in statement_seen:
                continue
            statement_seen.add(statement_key)
            db.add(
                MatterStatement(
                    matter_id=matter_id,
                    document_id=document.id,
                    page_id=page.id,
                    page_number=page.page_number,
                    kind=candidate.kind,
                    speaker_role=candidate.speaker_role,
                    raw_text=candidate.raw_text,
                    normalized_text=candidate.normalized_text,
                    confidence=candidate.confidence,
                    start_char=candidate.start_char,
                    end_char=candidate.end_char,
                    metadata_json={**candidate.metadata, "filename": document.filename},
                )
            )

    await db.flush()

    facts_by_key: dict[str, list[MatterFact]] = defaultdict(list)
    for fact in fact_map.values():
        if fact.status != FactStatus.REJECTED:
            facts_by_key[fact.fact_key].append(fact)

    for fact_key, facts in facts_by_key.items():
        if fact_key not in CONFLICT_FACT_KEYS:
            continue
        values = sorted({fact.normalized_value for fact in facts})
        if len(values) <= 1:
            continue

        label = _contradiction_label(fact_key, facts[0].label)
        contradiction_key = fact_key
        severity = SEVERITY_BY_FACT_KEY.get(fact_key, ContradictionSeverity.MEDIUM)
        value_payload = [
            {
                "fact_id": str(fact.id),
                "value": fact.normalized_value,
                "display": fact.value_text,
                "confidence": fact.confidence,
            }
            for fact in sorted(facts, key=lambda item: item.normalized_value)
        ]
        contradiction = MatterContradiction(
            matter_id=matter_id,
            contradiction_key=contradiction_key,
            fact_key=fact_key,
            label=label,
            explanation=(
                f"The matter contains {len(values)} different values for {label.lower()}. "
                "The system has not chosen which source is correct; lawyer review is required."
            ),
            severity=severity,
            status=prior_contradiction_status.get(
                contradiction_key, ContradictionStatus.OPEN
            ),
            values_json=value_payload,
            fact_ids_json=[str(fact.id) for fact in facts],
            metadata_json={"detector": "single_value_fact_conflict"},
        )
        db.add(contradiction)
        await db.flush()

        if contradiction.status == ContradictionStatus.OPEN:
            db.add(
                ReviewItem(
                    matter_id=matter_id,
                    item_type=ReviewItemType.CONTRADICTION,
                    target_id=str(contradiction.id),
                    title=f"Resolve contradiction: {label}",
                    reason=contradiction.explanation,
                    priority=(
                        ReviewPriority.HIGH
                        if severity == ContradictionSeverity.HIGH
                        else ReviewPriority.MEDIUM
                    ),
                    status=ReviewStatus.OPEN,
                    metadata_json={"fact_key": fact_key},
                )
            )

    # Low-confidence extracted facts are reviewable, but high-confidence rule matches do not create noise.
    for fact in fact_map.values():
        if fact.confidence >= 0.85 or fact.status != FactStatus.AUTO:
            continue
        db.add(
            ReviewItem(
                matter_id=matter_id,
                item_type=ReviewItemType.FACT,
                target_id=str(fact.id),
                title=f"Verify fact: {fact.label}",
                reason=f"Automatically extracted with {fact.confidence:.0%} confidence.",
                priority=ReviewPriority.LOW,
                status=ReviewStatus.OPEN,
                metadata_json={
                    "fact_key": fact.fact_key,
                    "normalized_value": fact.normalized_value,
                },
            )
        )

    await db.commit()
    summary = await get_intelligence_summary(db, matter_id)
    return RebuildResultRead(**summary.model_dump(), rebuilt=True)


async def _document_names(db: AsyncSession, document_ids: set[UUID]) -> dict[UUID, str]:
    if not document_ids:
        return {}
    rows = await db.execute(select(Document.id, Document.filename).where(Document.id.in_(document_ids)))
    return {row.id: row.filename for row in rows}


async def list_facts(db: AsyncSession, matter_id: UUID) -> list[FactRead]:
    await _ensure_matter(db, matter_id)
    stmt = (
        select(MatterFact)
        .where(MatterFact.matter_id == matter_id)
        .options(selectinload(MatterFact.sources))
        .order_by(MatterFact.category, MatterFact.label, MatterFact.normalized_value)
    )
    facts = list((await db.scalars(stmt)).unique().all())
    document_ids = {source.document_id for fact in facts for source in fact.sources}
    names = await _document_names(db, document_ids)
    return [
        FactRead(
            id=fact.id,
            matter_id=fact.matter_id,
            fact_key=fact.fact_key,
            fact_type=fact.fact_type,
            category=fact.category,
            label=fact.label,
            value_text=fact.value_text,
            normalized_value=fact.normalized_value,
            confidence=fact.confidence,
            status=fact.status,
            metadata_json=fact.metadata_json,
            sources=[
                SourceRead(
                    id=source.id,
                    document_id=source.document_id,
                    filename=names.get(source.document_id),
                    page_id=source.page_id,
                    page_number=source.page_number,
                    relation=source.relation,
                    quote=source.quote,
                    start_char=source.start_char,
                    end_char=source.end_char,
                    confidence=source.confidence,
                )
                for source in fact.sources
            ],
            created_at=fact.created_at,
            updated_at=fact.updated_at,
        )
        for fact in facts
    ]


async def update_fact_status(
    db: AsyncSession, fact_id: UUID, new_status: FactStatus
) -> FactRead:
    stmt = (
        select(MatterFact)
        .where(MatterFact.id == fact_id)
        .options(selectinload(MatterFact.sources))
    )
    fact = (await db.scalars(stmt)).unique().one_or_none()
    if fact is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    await _ensure_matter(db, fact.matter_id, required=MatterAccessLevel.WORK)
    fact.status = new_status
    await db.commit()
    facts = await list_facts(db, fact.matter_id)
    return next(item for item in facts if item.id == fact.id)


async def list_timeline(db: AsyncSession, matter_id: UUID) -> list[TimelineEventRead]:
    await _ensure_matter(db, matter_id)
    stmt = (
        select(TimelineEvent)
        .where(TimelineEvent.matter_id == matter_id)
        .options(selectinload(TimelineEvent.sources))
        .order_by(TimelineEvent.event_date, TimelineEvent.created_at)
    )
    events = list((await db.scalars(stmt)).unique().all())
    document_ids = {source.document_id for event in events for source in event.sources}
    names = await _document_names(db, document_ids)
    return [
        TimelineEventRead(
            id=event.id,
            matter_id=event.matter_id,
            event_key=event.event_key,
            event_type=event.event_type,
            event_date=event.event_date,
            title=event.title,
            description=event.description,
            confidence=event.confidence,
            metadata_json=event.metadata_json,
            sources=[
                TimelineSourceRead(
                    id=source.id,
                    document_id=source.document_id,
                    filename=names.get(source.document_id),
                    page_id=source.page_id,
                    page_number=source.page_number,
                    quote=source.quote,
                    start_char=source.start_char,
                    end_char=source.end_char,
                    confidence=source.confidence,
                )
                for source in event.sources
            ],
            created_at=event.created_at,
            updated_at=event.updated_at,
        )
        for event in events
    ]


async def list_statements(
    db: AsyncSession,
    matter_id: UUID,
    *,
    kind: StatementKind | None = None,
) -> list[StatementRead]:
    await _ensure_matter(db, matter_id)
    stmt = select(MatterStatement).where(MatterStatement.matter_id == matter_id)
    if kind is not None:
        stmt = stmt.where(MatterStatement.kind == kind)
    stmt = stmt.order_by(MatterStatement.created_at, MatterStatement.page_number)
    statements = list((await db.scalars(stmt)).all())
    names = await _document_names(db, {item.document_id for item in statements})
    return [
        StatementRead(
            id=item.id,
            matter_id=item.matter_id,
            document_id=item.document_id,
            filename=names.get(item.document_id),
            page_id=item.page_id,
            page_number=item.page_number,
            kind=item.kind,
            speaker_role=item.speaker_role,
            raw_text=item.raw_text,
            normalized_text=item.normalized_text,
            confidence=item.confidence,
            start_char=item.start_char,
            end_char=item.end_char,
            metadata_json=item.metadata_json,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in statements
    ]


async def list_contradictions(db: AsyncSession, matter_id: UUID) -> list[ContradictionRead]:
    await _ensure_matter(db, matter_id)
    stmt = (
        select(MatterContradiction)
        .where(MatterContradiction.matter_id == matter_id)
        .order_by(MatterContradiction.severity.desc(), MatterContradiction.created_at)
    )
    return [ContradictionRead.model_validate(item) for item in (await db.scalars(stmt)).all()]


async def update_contradiction_status(
    db: AsyncSession, contradiction_id: UUID, new_status: ContradictionStatus
) -> ContradictionRead:
    contradiction = await db.get(MatterContradiction, contradiction_id)
    if contradiction is None:
        raise HTTPException(status_code=404, detail="Contradiction not found")
    await _ensure_matter(db, contradiction.matter_id, required=MatterAccessLevel.WORK)
    contradiction.status = new_status
    await db.commit()
    await db.refresh(contradiction)
    return ContradictionRead.model_validate(contradiction)


async def list_review_items(db: AsyncSession, matter_id: UUID) -> list[ReviewItemRead]:
    await _ensure_matter(db, matter_id)
    stmt = (
        select(ReviewItem)
        .where(ReviewItem.matter_id == matter_id)
        .order_by(ReviewItem.status, ReviewItem.priority.desc(), ReviewItem.created_at)
    )
    return [ReviewItemRead.model_validate(item) for item in (await db.scalars(stmt)).all()]


async def update_review_status(
    db: AsyncSession, review_id: UUID, new_status: ReviewStatus
) -> ReviewItemRead:
    item = await db.get(ReviewItem, review_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    await _ensure_matter(db, item.matter_id, required=MatterAccessLevel.WORK)

    item.status = new_status

    # Keep the review decision and its generated target synchronized. The target remains source-backed
    # and can be regenerated later; human decisions are preserved by deterministic fact/conflict keys.
    try:
        target_uuid = UUID(item.target_id)
    except ValueError:
        target_uuid = None

    if target_uuid is not None and item.item_type == ReviewItemType.FACT:
        fact = await db.get(MatterFact, target_uuid)
        if fact is not None:
            if new_status == ReviewStatus.CONFIRMED:
                fact.status = FactStatus.CONFIRMED
            elif new_status == ReviewStatus.REJECTED:
                fact.status = FactStatus.REJECTED
    elif target_uuid is not None and item.item_type == ReviewItemType.CONTRADICTION:
        contradiction = await db.get(MatterContradiction, target_uuid)
        if contradiction is not None:
            if new_status == ReviewStatus.CONFIRMED:
                contradiction.status = ContradictionStatus.RESOLVED
            elif new_status in {ReviewStatus.REJECTED, ReviewStatus.DISMISSED}:
                contradiction.status = ContradictionStatus.DISMISSED

    await db.commit()
    await db.refresh(item)
    return ReviewItemRead.model_validate(item)


async def get_evidence_matrix(db: AsyncSession, matter_id: UUID) -> EvidenceMatrixRead:
    facts = await list_facts(db, matter_id)
    contradictions = await list_contradictions(db, matter_id)
    contradiction_by_fact_id: dict[str, MatterContradiction | ContradictionRead] = {}
    for contradiction in contradictions:
        if contradiction.status == ContradictionStatus.DISMISSED:
            continue
        for fact_id in contradiction.fact_ids_json:
            contradiction_by_fact_id[str(fact_id)] = contradiction

    statement_counts = Counter(
        statement.kind.value for statement in await list_statements(db, matter_id)
    )
    return EvidenceMatrixRead(
        matter_id=matter_id,
        facts=[
            EvidenceFactRead(
                fact=fact,
                contradiction_id=(
                    contradiction_by_fact_id.get(str(fact.id)).id
                    if str(fact.id) in contradiction_by_fact_id
                    else None
                ),
                contradiction_severity=(
                    contradiction_by_fact_id.get(str(fact.id)).severity
                    if str(fact.id) in contradiction_by_fact_id
                    else None
                ),
            )
            for fact in facts
            if fact.status != FactStatus.REJECTED
        ],
        statement_counts=dict(statement_counts),
    )


async def get_intelligence_summary(
    db: AsyncSession, matter_id: UUID
) -> IntelligenceSummaryRead:
    await _ensure_matter(db, matter_id)

    fact_count = await db.scalar(
        select(func.count(MatterFact.id)).where(
            MatterFact.matter_id == matter_id,
            MatterFact.status != FactStatus.REJECTED,
        )
    )
    event_count = await db.scalar(
        select(func.count(TimelineEvent.id)).where(TimelineEvent.matter_id == matter_id)
    )
    statement_rows = await db.execute(
        select(MatterStatement.kind, func.count(MatterStatement.id))
        .where(MatterStatement.matter_id == matter_id)
        .group_by(MatterStatement.kind)
    )
    statement_counts = {row[0].value: row[1] for row in statement_rows}
    contradiction_count = await db.scalar(
        select(func.count(MatterContradiction.id)).where(
            MatterContradiction.matter_id == matter_id,
            MatterContradiction.status == ContradictionStatus.OPEN,
        )
    )
    review_count = await db.scalar(
        select(func.count(ReviewItem.id)).where(
            ReviewItem.matter_id == matter_id,
            ReviewItem.status == ReviewStatus.OPEN,
        )
    )
    source_document_count = await db.scalar(
        select(func.count(func.distinct(MatterStatement.document_id))).where(
            MatterStatement.matter_id == matter_id
        )
    )
    # Facts can exist without statements, so document/page coverage is more accurately based on fact sources.
    fact_ids = select(MatterFact.id).where(MatterFact.matter_id == matter_id)
    fact_doc_count = await db.scalar(
        select(func.count(func.distinct(FactSource.document_id))).where(
            FactSource.fact_id.in_(fact_ids)
        )
    )
    page_count = await db.scalar(
        select(func.count(func.distinct(FactSource.page_id))).where(
            FactSource.fact_id.in_(fact_ids), FactSource.page_id.is_not(None)
        )
    )

    return IntelligenceSummaryRead(
        matter_id=matter_id,
        facts=int(fact_count or 0),
        timeline_events=int(event_count or 0),
        claims=int(statement_counts.get(StatementKind.CLAIM.value, 0)),
        admissions=int(statement_counts.get(StatementKind.ADMISSION.value, 0)),
        denials=int(statement_counts.get(StatementKind.DENIAL.value, 0)),
        contradictions=int(contradiction_count or 0),
        open_review_items=int(review_count or 0),
        source_documents=max(int(source_document_count or 0), int(fact_doc_count or 0)),
        source_pages=int(page_count or 0),
    )
