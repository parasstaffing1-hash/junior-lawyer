"""Populate one fully-worked litigation matter for a walkthrough.

The contract-review matter from seed_demo.py exercises document processing but
leaves the litigation screens empty: no issues, no evidence links, no
deadlines, so the agent reports zeros and issue standing has nothing to rank.
This seeds a matter that is far enough along to show those screens doing their
job.

Everything is fictional and labelled DEMO. Writes through the service layer's
models directly, so it needs the database but not a signed-in session.

    python scripts/seed_demo_litigation.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.models.evidence import (
    EvidenceGap,
    EvidenceIssueLink,
    EvidenceItem,
    EvidenceKind,
    EvidenceLinkType,
    EvidenceStrength,
    EvidenceReviewStatus,
    EvidenceWitness,
    EvidenceWitnessLink,
    GapStatus,
    LitigationIssue,
    WitnessKind,
)
from app.models.intelligence import (
    ContradictionSeverity,
    ContradictionStatus,
    MatterContradiction,
    TimelineEvent,
)
from app.models.matter import Matter
from app.models.procedure import DeadlineStatus, MatterDeadline

TITLE = "Sharma Transport v. Verma Logistics (DEMO)"

TODAY = date.today()


async def main() -> int:
    async with AsyncSessionLocal() as db:
        existing = (await db.scalars(select(Matter).where(Matter.title == TITLE))).first()
        if existing is not None:
            # Re-running should refresh the demo, not stack a second copy of it.
            print(f"existing demo matter found ({existing.id}) — clearing its litigation data")
            for model in (
                EvidenceWitnessLink,
                EvidenceIssueLink,
                EvidenceGap,
                EvidenceWitness,
                EvidenceItem,
                LitigationIssue,
                MatterContradiction,
                TimelineEvent,
                MatterDeadline,
            ):
                await db.execute(delete(model).where(model.matter_id == existing.id))
            matter = existing
        else:
            matter = Matter(
                title=TITLE,
                client_name="Sharma Transport Private Limited",
                court_name="District Court, Nagpur",
                case_number="COMS 412/2026",
                jurisdiction="Maharashtra",
                description=(
                    "Suit for recovery of freight charges and damages for short-delivery "
                    "of consignments under a carriage contract."
                ),
            )
            db.add(matter)
            await db.flush()
        print(f"matter {matter.id}")

        # --- issues -----------------------------------------------------
        issues = {
            "breach": LitigationIssue(
                matter_id=matter.id,
                code="breach_of_contract",
                title="Whether the carriage contract was breached",
                description="Short-delivery of 4 of 11 consignments between March and June.",
                burden_side="plaintiff",
                priority=1,
            ),
            "quantum": LitigationIssue(
                matter_id=matter.id,
                code="quantum_of_damages",
                title="Quantum of damages payable",
                description="Freight withheld, replacement cost and demurrage claimed.",
                burden_side="plaintiff",
                priority=2,
            ),
            "limitation": LitigationIssue(
                matter_id=matter.id,
                code="limitation",
                title="Whether the suit is within limitation",
                description="Article 55 — three years from the date the contract was broken.",
                burden_side="defendant",
                priority=1,
            ),
            "jurisdiction": LitigationIssue(
                matter_id=matter.id,
                code="territorial_jurisdiction",
                title="Whether the Nagpur court has territorial jurisdiction",
                description="Consignment note carries a Pune exclusive-jurisdiction clause.",
                burden_side="defendant",
                priority=3,
            ),
        }
        db.add_all(issues.values())
        await db.flush()

        # --- evidence ---------------------------------------------------
        items = {
            "contract": EvidenceItem(
                matter_id=matter.id,
                title="Carriage agreement dated 12 January 2024",
                kind=EvidenceKind.CONTRACT,
                strength=EvidenceStrength.HIGH,
                review_status=EvidenceReviewStatus.REVIEWED,
                authenticity_checked=True,
                admissibility_checked=True,
                confidence=0.95,
                summary="Signed by both parties. Clause 9 fixes liability for short-delivery.",
            ),
            "notes": EvidenceItem(
                matter_id=matter.id,
                title="Consignment notes 4471–4481",
                kind=EvidenceKind.COURT_FILING,
                strength=EvidenceStrength.HIGH,
                review_status=EvidenceReviewStatus.REVIEWED,
                authenticity_checked=True,
                confidence=0.9,
                summary="Eleven notes; four bear the consignee's short-delivery endorsement.",
            ),
            "ledger": EvidenceItem(
                matter_id=matter.id,
                title="Plaintiff's freight ledger extract",
                kind=EvidenceKind.FINANCIAL,
                strength=EvidenceStrength.MEDIUM,
                confidence=0.7,
                summary="Shows ₹18,40,000 outstanding as at 30 June 2024.",
            ),
            "emails": EvidenceItem(
                matter_id=matter.id,
                title="Email chain, March–May 2024",
                kind=EvidenceKind.CORRESPONDENCE,
                strength=EvidenceStrength.MEDIUM,
                confidence=0.65,
                summary="Defendant acknowledges two shortfalls, disputes the other two.",
            ),
            "reply": EvidenceItem(
                matter_id=matter.id,
                title="Defendant's reply notice dated 2 August 2024",
                kind=EvidenceKind.CORRESPONDENCE,
                strength=EvidenceStrength.HIGH,
                review_status=EvidenceReviewStatus.REVIEWED,
                confidence=0.85,
                summary="Denies breach; relies on the Pune jurisdiction clause.",
            ),
            "gatepass": EvidenceItem(
                matter_id=matter.id,
                title="Warehouse gate passes (partial)",
                kind=EvidenceKind.OTHER,
                strength=EvidenceStrength.LOW,
                confidence=0.4,
                summary="Only 6 of 11 gate passes are on the file.",
            ),
        }
        db.add_all(items.values())
        await db.flush()

        # --- links ------------------------------------------------------
        def link(item, issue, kind, confidence, rationale):
            return EvidenceIssueLink(
                matter_id=matter.id,
                evidence_item_id=items[item].id,
                issue_id=issues[issue].id,
                link_type=kind,
                confidence=confidence,
                rationale=rationale,
                source="manual",
            )

        db.add_all(
            [
                link("contract", "breach", EvidenceLinkType.SUPPORTS, 0.95, "Clause 9 fixes liability."),
                link("notes", "breach", EvidenceLinkType.SUPPORTS, 0.9, "Endorsements record the shortfall."),
                link("emails", "breach", EvidenceLinkType.SUPPORTS, 0.7, "Two shortfalls admitted."),
                link("reply", "breach", EvidenceLinkType.CONTRADICTS, 0.8, "Breach denied in terms."),
                link("gatepass", "breach", EvidenceLinkType.SUPPORTS, 0.35, "Incomplete series."),
                link("ledger", "quantum", EvidenceLinkType.SUPPORTS, 0.8, "Outstanding computed."),
                link("contract", "quantum", EvidenceLinkType.SUPPORTS, 0.6, "Rate card at Schedule B."),
                link("reply", "quantum", EvidenceLinkType.CONTRADICTS, 0.7, "Quantum disputed as inflated."),
                link("notes", "limitation", EvidenceLinkType.SUPPORTS, 0.85, "Fixes the accrual dates."),
                link("contract", "jurisdiction", EvidenceLinkType.CONTRADICTS, 0.75, "Pune exclusive-jurisdiction clause."),
                link("notes", "jurisdiction", EvidenceLinkType.SUPPORTS, 0.5, "Delivery performed at Nagpur."),
            ]
        )

        # --- witnesses --------------------------------------------------
        witnesses = {
            "pw1": EvidenceWitness(
                matter_id=matter.id, name="PW-1 R. Sharma", normalized_name="pw-1 r. sharma",
                kind=WitnessKind.PARTY, side="plaintiff", role="Managing Director",
            ),
            "pw3": EvidenceWitness(
                matter_id=matter.id, name="PW-3 S. Kulkarni", normalized_name="pw-3 s. kulkarni",
                kind=WitnessKind.FACT, side="plaintiff", role="Warehouse supervisor, Nagpur",
            ),
            "dw1": EvidenceWitness(
                matter_id=matter.id, name="DW-1 A. Verma", normalized_name="dw-1 a. verma",
                kind=WitnessKind.PARTY, side="defendant", role="Partner",
            ),
        }
        db.add_all(witnesses.values())
        await db.flush()
        db.add_all(
            [
                EvidenceWitnessLink(matter_id=matter.id, witness_id=witnesses["pw3"].id, evidence_item_id=items["notes"].id, relationship="attests", confidence=0.9),
                EvidenceWitnessLink(matter_id=matter.id, witness_id=witnesses["pw3"].id, evidence_item_id=items["gatepass"].id, relationship="attests", confidence=0.6),
                EvidenceWitnessLink(matter_id=matter.id, witness_id=witnesses["pw1"].id, evidence_item_id=items["ledger"].id, relationship="proves", confidence=0.8),
                EvidenceWitnessLink(matter_id=matter.id, witness_id=witnesses["dw1"].id, evidence_item_id=items["reply"].id, relationship="authored", confidence=0.9),
            ]
        )

        # --- gaps -------------------------------------------------------
        db.add_all(
            [
                EvidenceGap(
                    matter_id=matter.id, issue_id=issues["breach"].id, gap_key="gate_passes",
                    title="Gate passes for consignments 4475–4479",
                    explanation="Five of eleven gate passes are not on the file; the endorsement series is incomplete without them.",
                    severity="high", status=GapStatus.OPEN,
                    suggested_action="Request certified copies from the Nagpur warehouse before evidence closes.",
                ),
                EvidenceGap(
                    matter_id=matter.id, issue_id=issues["quantum"].id, gap_key="replacement_invoices",
                    title="Replacement purchase invoices",
                    explanation="Damages include replacement cost, but no purchase invoices are filed.",
                    severity="medium", status=GapStatus.OPEN,
                    suggested_action="Obtain invoices from the consignee and file with a supplementary list.",
                ),
            ]
        )

        # --- timeline ---------------------------------------------------
        events = [
            ("2024-01-12", "contract", "Carriage agreement executed"),
            ("2024-03-04", "breach", "First short-delivery recorded (consignment 4473)"),
            ("2024-06-18", "breach", "Fourth short-delivery recorded (consignment 4481)"),
            ("2024-07-11", "notice", "Demand notice issued to the defendant"),
            ("2024-08-02", "notice", "Reply notice received denying liability"),
            ("2026-02-20", "filing", "Plaint filed before the District Court, Nagpur"),
            ("2026-05-06", "hearing", "Written statement filed by the defendant"),
            ("2026-07-22", "hearing", "Issues framed"),
        ]
        for iso, kind, title in events:
            db.add(
                TimelineEvent(
                    matter_id=matter.id, event_key=f"{kind}:{iso}", event_type=kind,
                    event_date=date.fromisoformat(iso), title=title,
                    description=f"DEMO record — {title}.", confidence=1.0,
                )
            )

        # --- contradictions ---------------------------------------------
        db.add_all(
            [
                MatterContradiction(
                    matter_id=matter.id, contradiction_key="shortfall_count",
                    fact_key="consignments_short", label="Number of short-delivered consignments",
                    explanation="Plaint pleads four; the defendant's emails admit two and dispute two.",
                    severity=ContradictionSeverity.HIGH, status=ContradictionStatus.OPEN,
                ),
                MatterContradiction(
                    matter_id=matter.id, contradiction_key="amount_outstanding",
                    fact_key="amount_outstanding", label="Amount outstanding",
                    explanation="Ledger shows ₹18,40,000; the demand notice claims ₹21,05,000.",
                    severity=ContradictionSeverity.MEDIUM, status=ContradictionStatus.OPEN,
                ),
            ]
        )

        # --- deadlines --------------------------------------------------
        def deadline(title, due_in_days, status, trigger_iso, note):
            due = TODAY + timedelta(days=due_in_days)
            return MatterDeadline(
                matter_id=matter.id, title=title, trigger_type="manual",
                trigger_date=date.fromisoformat(trigger_iso), calculated_date=due,
                due_date=due, status=status, reviewed_by_lawyer=True,
                authority_json={"note": note},
            )

        db.add_all(
            [
                deadline("Limitation expiry — Article 55", 210, DeadlineStatus.UPCOMING, "2024-06-18", "Limitation Act, 1963, Article 55."),
                deadline("File list of documents", 6, DeadlineStatus.UPCOMING, "2026-07-22", "CPC Order 7 Rule 14."),
                deadline("Serve interrogatories", 12, DeadlineStatus.UPCOMING, "2026-07-22", "CPC Order 11."),
                deadline("Reply to defendant's application", -3, DeadlineStatus.OVERDUE, "2026-08-01", "Directed at the hearing on 1 August."),
            ]
        )

        await db.commit()

    print("\nseeded litigation demo matter:")
    print(f"  {TITLE}")
    print("  4 issues, 6 evidence items, 11 issue links, 3 witnesses, 2 gaps,")
    print("  8 timeline events, 2 contradictions, 4 deadlines (1 overdue)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
