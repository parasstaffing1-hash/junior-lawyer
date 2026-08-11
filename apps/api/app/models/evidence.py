from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class EvidenceKind(StrEnum):
    COURT_FILING = "court_filing"
    COURT_ORDER = "court_order"
    CONTRACT = "contract"
    CORRESPONDENCE = "correspondence"
    FINANCIAL = "financial"
    IDENTITY = "identity"
    PROPERTY = "property"
    ELECTRONIC = "electronic"
    PHOTO_VIDEO = "photo_video"
    WITNESS_STATEMENT = "witness_statement"
    EXPERT = "expert"
    OTHER = "other"


class EvidenceStrength(StrEnum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceReviewStatus(StrEnum):
    AUTO = "auto"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


class EvidenceLinkType(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class GapStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class BundleStatus(StrEnum):
    DRAFT = "draft"
    FINAL = "final"


class ExhibitStatus(StrEnum):
    PROPOSED = "proposed"
    MARKED = "marked"
    ADMITTED = "admitted"
    REJECTED = "rejected"


class WitnessKind(StrEnum):
    FACT = "fact"
    EXPERT = "expert"
    FORMAL = "formal"
    PARTY = "party"
    UNKNOWN = "unknown"


class WitnessPrepStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    USED = "used"


class LitigationIssue(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "litigation_issues"
    __table_args__ = (UniqueConstraint("matter_id", "code", name="uq_litigation_issue_matter_code"),)

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    burden_side: Mapped[str | None] = mapped_column(String(80), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, index=True)
    source: Mapped[str] = mapped_column(String(80), default="manual", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EvidenceItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evidence_items"
    __table_args__ = (UniqueConstraint("matter_id", "document_id", name="uq_evidence_item_matter_document"),)

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(400), index=True)
    kind: Mapped[EvidenceKind] = mapped_column(Enum(EvidenceKind, native_enum=False), default=EvidenceKind.OTHER, index=True)
    strength: Mapped[EvidenceStrength] = mapped_column(Enum(EvidenceStrength, native_enum=False), default=EvidenceStrength.UNKNOWN, index=True)
    review_status: Mapped[EvidenceReviewStatus] = mapped_column(Enum(EvidenceReviewStatus, native_enum=False), default=EvidenceReviewStatus.AUTO, index=True)
    authenticity_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    admissibility_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    original_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EvidenceIssueLink(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evidence_issue_links"
    __table_args__ = (UniqueConstraint("evidence_item_id", "issue_id", "link_type", name="uq_evidence_issue_link"),)

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    evidence_item_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_items.id", ondelete="CASCADE"), index=True)
    issue_id: Mapped[UUID] = mapped_column(ForeignKey("litigation_issues.id", ondelete="CASCADE"), index=True)
    link_type: Mapped[EvidenceLinkType] = mapped_column(Enum(EvidenceLinkType, native_enum=False), default=EvidenceLinkType.SUPPORTS, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    rationale: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), default="deterministic", index=True)


class EvidenceWitness(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evidence_witnesses"
    __table_args__ = (UniqueConstraint("matter_id", "normalized_name", name="uq_evidence_witness_matter_name"),)

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)
    kind: Mapped[WitnessKind] = mapped_column(Enum(WitnessKind, native_enum=False), default=WitnessKind.UNKNOWN, index=True)
    side: Mapped[str | None] = mapped_column(String(80), index=True)
    role: Mapped[str | None] = mapped_column(String(220))
    contact_ref: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), default="manual", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EvidenceWitnessLink(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evidence_witness_links"
    __table_args__ = (UniqueConstraint("witness_id", "evidence_item_id", name="uq_witness_evidence_link"),)

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    witness_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_witnesses.id", ondelete="CASCADE"), index=True)
    evidence_item_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_items.id", ondelete="CASCADE"), index=True)
    relationship: Mapped[str] = mapped_column(String(160), default="mentions", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    rationale: Mapped[str | None] = mapped_column(Text)


class EvidenceGap(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evidence_gaps"
    __table_args__ = (UniqueConstraint("matter_id", "gap_key", name="uq_evidence_gap_matter_key"),)

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    issue_id: Mapped[UUID | None] = mapped_column(ForeignKey("litigation_issues.id", ondelete="CASCADE"), nullable=True, index=True)
    gap_key: Mapped[str] = mapped_column(String(260), index=True)
    title: Mapped[str] = mapped_column(String(350))
    explanation: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(40), default="medium", index=True)
    status: Mapped[GapStatus] = mapped_column(Enum(GapStatus, native_enum=False), default=GapStatus.OPEN, index=True)
    suggested_action: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EvidenceBundle(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evidence_bundles"

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(350), index=True)
    bundle_type: Mapped[str] = mapped_column(String(80), default="hearing", index=True)
    status: Mapped[BundleStatus] = mapped_column(Enum(BundleStatus, native_enum=False), default=BundleStatus.DRAFT, index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(1000))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EvidenceBundleItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evidence_bundle_items"
    __table_args__ = (UniqueConstraint("bundle_id", "evidence_item_id", name="uq_bundle_evidence_item"),)

    bundle_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_bundles.id", ondelete="CASCADE"), index=True)
    evidence_item_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_items.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, index=True)
    section_label: Mapped[str | None] = mapped_column(String(220))
    included_reason: Mapped[str | None] = mapped_column(Text)


class EvidenceExhibit(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "evidence_exhibits"
    __table_args__ = (UniqueConstraint("matter_id", "label", name="uq_evidence_exhibit_matter_label"),)

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    evidence_item_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_items.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[ExhibitStatus] = mapped_column(Enum(ExhibitStatus, native_enum=False), default=ExhibitStatus.PROPOSED, index=True)
    marked_date: Mapped[str | None] = mapped_column(String(30))
    court_reference: Mapped[str | None] = mapped_column(String(250))
    notes: Mapped[str | None] = mapped_column(Text)


class WitnessPrepQuestion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "witness_prep_questions"

    matter_id: Mapped[UUID] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    witness_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_witnesses.id", ondelete="CASCADE"), index=True)
    issue_id: Mapped[UUID | None] = mapped_column(ForeignKey("litigation_issues.id", ondelete="SET NULL"), nullable=True, index=True)
    evidence_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("evidence_items.id", ondelete="SET NULL"), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(80), default="foundation", index=True)
    status: Mapped[WitnessPrepStatus] = mapped_column(Enum(WitnessPrepStatus, native_enum=False), default=WitnessPrepStatus.DRAFT, index=True)
    source: Mapped[str] = mapped_column(String(80), default="deterministic", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
