"""Exercises the per-issue evidence rollup against a real (in-memory) database.

The arithmetic is the point: a support ratio that quietly counts an unassessed
document as heavily as a proved one, or that reports 0% when nothing has been
linked at all, would mislead a lawyer reading the file.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.evidence import (
    EvidenceGap,
    EvidenceIssueLink,
    EvidenceItem,
    EvidenceLinkType,
    EvidenceStrength,
    EvidenceWitness,
    EvidenceWitnessLink,
    GapStatus,
    LitigationIssue,
)
from app.models.matter import Matter
from app.services.evidence.standing import compute_issue_standing


@pytest.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _matter(db: AsyncSession) -> Matter:
    matter = Matter(title="Test matter", jurisdiction="India")
    db.add(matter)
    await db.flush()
    return matter


def _item(matter_id, title: str, strength: EvidenceStrength) -> EvidenceItem:
    return EvidenceItem(matter_id=matter_id, title=title, strength=strength)


async def test_returns_empty_when_no_issues(db: AsyncSession) -> None:
    matter = await _matter(db)
    assert await compute_issue_standing(db, matter.id) == []


async def test_ratio_is_none_when_nothing_linked(db: AsyncSession) -> None:
    """Unknown, not unsupported. A 0% would read as 'we looked and found none'."""
    matter = await _matter(db)
    db.add(LitigationIssue(matter_id=matter.id, code="neg", title="Negligence"))
    await db.flush()

    rows = await compute_issue_standing(db, matter.id)
    assert len(rows) == 1
    assert rows[0]["support_ratio"] is None
    assert rows[0]["evidence_recorded"] is False


async def test_strength_and_confidence_both_weight_the_ratio(db: AsyncSession) -> None:
    matter = await _matter(db)
    issue = LitigationIssue(matter_id=matter.id, code="neg", title="Negligence")
    strong = _item(matter.id, "Expert report", EvidenceStrength.HIGH)
    weak = _item(matter.id, "Unassessed note", EvidenceStrength.UNKNOWN)
    db.add_all([issue, strong, weak])
    await db.flush()

    # HIGH at full confidence supports; UNKNOWN at full confidence contradicts.
    db.add_all(
        [
            EvidenceIssueLink(
                matter_id=matter.id,
                evidence_item_id=strong.id,
                issue_id=issue.id,
                link_type=EvidenceLinkType.SUPPORTS,
                confidence=1.0,
            ),
            EvidenceIssueLink(
                matter_id=matter.id,
                evidence_item_id=weak.id,
                issue_id=issue.id,
                link_type=EvidenceLinkType.CONTRADICTS,
                confidence=1.0,
            ),
        ]
    )
    await db.flush()

    row = (await compute_issue_standing(db, matter.id))[0]
    assert row["supporting_count"] == 1
    assert row["contradicting_count"] == 1
    # 1.0 support against 0.2 contradiction — not the 50% a naive count gives.
    assert row["support_weight"] == pytest.approx(1.0)
    assert row["contradict_weight"] == pytest.approx(0.2)
    assert row["support_ratio"] == pytest.approx(1.0 / 1.2, rel=1e-3)


async def test_only_supporting_evidence_creates_a_witness_dependency(db: AsyncSession) -> None:
    """Losing a witness who props up the other side's document is not this
    issue's exposure, so they must not appear as a dependency."""
    matter = await _matter(db)
    issue = LitigationIssue(matter_id=matter.id, code="neg", title="Negligence")
    ours = _item(matter.id, "Our affidavit", EvidenceStrength.MEDIUM)
    theirs = _item(matter.id, "Their affidavit", EvidenceStrength.MEDIUM)
    db.add_all([issue, ours, theirs])
    await db.flush()

    pw3 = EvidenceWitness(matter_id=matter.id, name="PW-3", normalized_name="pw-3")
    dw1 = EvidenceWitness(matter_id=matter.id, name="DW-1", normalized_name="dw-1")
    db.add_all([pw3, dw1])
    await db.flush()

    db.add_all(
        [
            EvidenceIssueLink(
                matter_id=matter.id,
                evidence_item_id=ours.id,
                issue_id=issue.id,
                link_type=EvidenceLinkType.SUPPORTS,
                confidence=0.8,
            ),
            EvidenceIssueLink(
                matter_id=matter.id,
                evidence_item_id=theirs.id,
                issue_id=issue.id,
                link_type=EvidenceLinkType.CONTRADICTS,
                confidence=0.8,
            ),
            EvidenceWitnessLink(
                matter_id=matter.id, witness_id=pw3.id, evidence_item_id=ours.id
            ),
            EvidenceWitnessLink(
                matter_id=matter.id, witness_id=dw1.id, evidence_item_id=theirs.id
            ),
        ]
    )
    await db.flush()

    row = (await compute_issue_standing(db, matter.id))[0]
    names = [w["name"] for w in row["depends_on_witnesses"]]
    assert names == ["PW-3"]


async def test_open_gaps_attach_to_their_issue(db: AsyncSession) -> None:
    matter = await _matter(db)
    issue = LitigationIssue(matter_id=matter.id, code="neg", title="Negligence")
    other = LitigationIssue(matter_id=matter.id, code="lim", title="Limitation")
    db.add_all([issue, other])
    await db.flush()

    db.add_all(
        [
            EvidenceGap(
                matter_id=matter.id,
                issue_id=issue.id,
                gap_key="cctv",
                title="CCTV footage",
                explanation="Referred to but not on file.",
                status=GapStatus.OPEN,
            ),
            EvidenceGap(
                matter_id=matter.id,
                issue_id=other.id,
                gap_key="notice",
                title="Proof of service",
                explanation="Not on file.",
                status=GapStatus.RESOLVED,
            ),
        ]
    )
    await db.flush()

    rows = {r["code"]: r for r in await compute_issue_standing(db, matter.id)}
    assert [g["title"] for g in rows["neg"]["open_gaps"]] == ["CCTV footage"]
    # A resolved gap is not an open one.
    assert rows["lim"]["open_gaps"] == []


async def test_issues_without_evidence_sort_last(db: AsyncSession) -> None:
    matter = await _matter(db)
    known = LitigationIssue(matter_id=matter.id, code="known", title="Has evidence")
    unknown = LitigationIssue(matter_id=matter.id, code="unknown", title="No evidence")
    item = _item(matter.id, "Contract", EvidenceStrength.HIGH)
    db.add_all([known, unknown, item])
    await db.flush()
    db.add(
        EvidenceIssueLink(
            matter_id=matter.id,
            evidence_item_id=item.id,
            issue_id=known.id,
            link_type=EvidenceLinkType.SUPPORTS,
            confidence=1.0,
        )
    )
    await db.flush()

    codes = [r["code"] for r in await compute_issue_standing(db, matter.id)]
    assert codes == ["known", "unknown"]


async def test_links_to_missing_items_are_ignored(db: AsyncSession) -> None:
    """A dangling link must not crash the rollup or inflate a count."""
    matter = await _matter(db)
    issue = LitigationIssue(matter_id=matter.id, code="neg", title="Negligence")
    db.add(issue)
    await db.flush()
    db.add(
        EvidenceIssueLink(
            matter_id=matter.id,
            evidence_item_id=uuid4(),
            issue_id=issue.id,
            link_type=EvidenceLinkType.SUPPORTS,
            confidence=1.0,
        )
    )
    await db.flush()

    row = (await compute_issue_standing(db, matter.id))[0]
    assert row["supporting_count"] == 0
    assert row["support_ratio"] is None
