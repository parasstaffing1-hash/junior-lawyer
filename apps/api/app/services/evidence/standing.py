"""How each litigation issue actually stands on the evidence.

The graph this reads was already here: issues, evidence items, the links
between them with a type and a confidence, the witnesses each item depends on,
and the recorded gaps. What was missing was the rollup — nothing answered "how
does the negligence issue stand?" without a human reading the whole matrix.

The score is deliberately a ratio of recorded support to recorded contradiction,
not a prediction. It says how the file currently stands, which is a question
about the file. Whether the issue will succeed is a question about the law, the
tribunal and the advocacy, and nothing here is entitled to an opinion on it.
Every input is returned alongside the number so a lawyer can see what moved it.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.evidence import service
from app.services.security.context import ActorContext
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

#: An item's strength multiplies the confidence of its link. UNKNOWN is not
#: zero — an unassessed document still sits on the file — but it counts least.
_STRENGTH_WEIGHT = {
    EvidenceStrength.HIGH: 1.0,
    EvidenceStrength.MEDIUM: 0.65,
    EvidenceStrength.LOW: 0.35,
    EvidenceStrength.UNKNOWN: 0.2,
}


def _weight(item: EvidenceItem, link: EvidenceIssueLink) -> float:
    return round(_STRENGTH_WEIGHT.get(item.strength, 0.2) * float(link.confidence or 0.0), 4)


async def issue_standing(db: AsyncSession, actor: ActorContext, matter_id: UUID) -> list[dict]:
    """Access-checked entry point used by the route."""
    await service._access(db, actor, matter_id)
    return await compute_issue_standing(db, matter_id)


async def compute_issue_standing(db: AsyncSession, matter_id: UUID) -> list[dict]:
    """One row per issue, heaviest-supported first.

    Kept separate from the access check so the arithmetic can be exercised
    without standing up an organization, a membership and a session.

    Reads the whole matter in five queries rather than per-issue, because a
    matter with thirty issues would otherwise cost a hundred round trips.
    """
    issues = list(
        (
            await db.scalars(
                select(LitigationIssue)
                .where(LitigationIssue.matter_id == matter_id)
                .order_by(LitigationIssue.priority, LitigationIssue.title)
            )
        ).all()
    )
    if not issues:
        return []

    links = list(
        (
            await db.scalars(
                select(EvidenceIssueLink).where(EvidenceIssueLink.matter_id == matter_id)
            )
        ).all()
    )
    items = {
        item.id: item
        for item in (
            await db.scalars(select(EvidenceItem).where(EvidenceItem.matter_id == matter_id))
        ).all()
    }
    gaps = list(
        (
            await db.scalars(
                select(EvidenceGap).where(
                    EvidenceGap.matter_id == matter_id, EvidenceGap.status == GapStatus.OPEN
                )
            )
        ).all()
    )
    witness_links = list(
        (
            await db.scalars(
                select(EvidenceWitnessLink).where(EvidenceWitnessLink.matter_id == matter_id)
            )
        ).all()
    )
    witnesses = {
        w.id: w
        for w in (
            await db.scalars(select(EvidenceWitness).where(EvidenceWitness.matter_id == matter_id))
        ).all()
    }

    witnesses_by_item: dict[UUID, list[EvidenceWitness]] = {}
    for link in witness_links:
        witness = witnesses.get(link.witness_id)
        if witness is not None:
            witnesses_by_item.setdefault(link.evidence_item_id, []).append(witness)

    rows: list[dict] = []
    for issue in issues:
        issue_links = [link for link in links if link.issue_id == issue.id]
        supporting: list[dict] = []
        contradicting: list[dict] = []
        support_weight = 0.0
        contradict_weight = 0.0
        depends_on: dict[UUID, dict] = {}

        for link in issue_links:
            item = items.get(link.evidence_item_id)
            if item is None:
                continue
            weight = _weight(item, link)
            entry = {
                "evidence_item_id": str(item.id),
                "title": item.title,
                "kind": str(item.kind),
                "strength": str(item.strength),
                "link_confidence": round(float(link.confidence or 0.0), 3),
                "weight": weight,
                "rationale": link.rationale,
            }
            if link.link_type is EvidenceLinkType.SUPPORTS:
                supporting.append(entry)
                support_weight += weight
                # Only supporting evidence creates a dependency worth flagging:
                # losing a witness who props up the other side's document is
                # not this issue's exposure.
                for witness in witnesses_by_item.get(item.id, []):
                    depends_on.setdefault(
                        witness.id,
                        {
                            "witness_id": str(witness.id),
                            "name": witness.name,
                            "kind": str(witness.kind),
                            "side": witness.side,
                            "supports_items": 0,
                        },
                    )
                    depends_on[witness.id]["supports_items"] += 1
            elif link.link_type is EvidenceLinkType.CONTRADICTS:
                contradicting.append(entry)
                contradict_weight += weight

        total = support_weight + contradict_weight
        # No recorded evidence either way is *unknown*, not zero support. The
        # difference matters: one is "we looked", the other is "we have not".
        support_ratio = round(support_weight / total, 4) if total > 0 else None

        issue_gaps = [g for g in gaps if g.issue_id == issue.id]
        supporting.sort(key=lambda e: e["weight"], reverse=True)
        contradicting.sort(key=lambda e: e["weight"], reverse=True)

        rows.append(
            {
                "issue_id": str(issue.id),
                "code": issue.code,
                "title": issue.title,
                "burden_side": issue.burden_side,
                "priority": issue.priority,
                "support_ratio": support_ratio,
                "support_weight": round(support_weight, 4),
                "contradict_weight": round(contradict_weight, 4),
                "supporting_count": len(supporting),
                "contradicting_count": len(contradicting),
                "supporting": supporting[:10],
                "contradicting": contradicting[:10],
                "open_gaps": [
                    {
                        "gap_id": str(g.id),
                        "title": g.title,
                        "severity": g.severity,
                        "suggested_action": g.suggested_action,
                    }
                    for g in issue_gaps
                ],
                "depends_on_witnesses": sorted(
                    depends_on.values(), key=lambda w: w["supports_items"], reverse=True
                ),
                "evidence_recorded": total > 0,
            }
        )

    rows.sort(key=lambda r: (r["support_ratio"] is None, -(r["support_ratio"] or 0)))
    return rows
