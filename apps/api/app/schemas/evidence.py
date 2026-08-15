from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.evidence import (
    BundleStatus, EvidenceKind, EvidenceLinkType, EvidenceReviewStatus, EvidenceStrength,
    ExhibitStatus, GapStatus, WitnessKind, WitnessPrepStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IssueCreate(BaseModel):
    code: str = Field(min_length=2, max_length=160)
    title: str = Field(min_length=2, max_length=300)
    description: str | None = None
    burden_side: str | None = None
    priority: int = Field(default=3, ge=1, le=5)


class IssueRead(ORMModel):
    id: UUID
    matter_id: UUID
    code: str
    title: str
    description: str | None
    burden_side: str | None
    priority: int
    source: str
    metadata_json: dict
    created_at: datetime


class EvidenceItemRead(ORMModel):
    id: UUID
    matter_id: UUID
    document_id: UUID | None
    title: str
    kind: EvidenceKind
    strength: EvidenceStrength
    review_status: EvidenceReviewStatus
    authenticity_checked: bool
    admissibility_checked: bool
    original_available: bool | None
    confidence: float
    summary: str | None
    metadata_json: dict
    created_at: datetime


class EvidenceItemUpdate(BaseModel):
    kind: EvidenceKind | None = None
    strength: EvidenceStrength | None = None
    review_status: EvidenceReviewStatus | None = None
    authenticity_checked: bool | None = None
    admissibility_checked: bool | None = None
    original_available: bool | None = None
    summary: str | None = None


class IssueLinkCreate(BaseModel):
    issue_id: UUID
    link_type: EvidenceLinkType = EvidenceLinkType.SUPPORTS
    rationale: str | None = None


class IssueLinkRead(ORMModel):
    id: UUID
    matter_id: UUID
    evidence_item_id: UUID
    issue_id: UUID
    link_type: EvidenceLinkType
    confidence: float
    rationale: str | None
    source: str


class WitnessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=300)
    kind: WitnessKind = WitnessKind.UNKNOWN
    side: str | None = None
    role: str | None = None
    notes: str | None = None


class WitnessRead(ORMModel):
    id: UUID
    matter_id: UUID
    name: str
    normalized_name: str
    kind: WitnessKind
    side: str | None
    role: str | None
    notes: str | None
    source: str
    metadata_json: dict
    created_at: datetime


class WitnessLinkCreate(BaseModel):
    evidence_item_id: UUID
    relationship: str = "mentions"
    rationale: str | None = None


class WitnessLinkRead(ORMModel):
    id: UUID
    matter_id: UUID
    witness_id: UUID
    evidence_item_id: UUID
    relationship: str
    confidence: float
    rationale: str | None


class GapRead(ORMModel):
    id: UUID
    matter_id: UUID
    issue_id: UUID | None
    gap_key: str
    title: str
    explanation: str
    severity: str
    status: GapStatus
    suggested_action: str | None
    metadata_json: dict
    created_at: datetime


class GapUpdate(BaseModel):
    status: GapStatus


class ExhibitCreate(BaseModel):
    evidence_item_id: UUID
    label: str = Field(min_length=1, max_length=120)
    notes: str | None = None


class ExhibitRead(ORMModel):
    id: UUID
    matter_id: UUID
    evidence_item_id: UUID
    label: str
    status: ExhibitStatus
    marked_date: str | None
    court_reference: str | None
    notes: str | None


class ExhibitUpdate(BaseModel):
    status: ExhibitStatus | None = None
    marked_date: str | None = None
    court_reference: str | None = None
    notes: str | None = None


class BundleCreate(BaseModel):
    title: str = Field(min_length=2, max_length=350)
    bundle_type: str = Field(default="hearing", max_length=80)
    evidence_item_ids: list[UUID] = Field(default_factory=list)
    issue_ids: list[UUID] = Field(default_factory=list)
    description: str | None = None


class BundleRead(ORMModel):
    id: UUID
    matter_id: UUID
    title: str
    bundle_type: str
    status: BundleStatus
    created_by_user_id: UUID | None
    description: str | None
    sha256: str | None
    storage_key: str | None
    metadata_json: dict
    created_at: datetime


class BundleItemRead(ORMModel):
    id: UUID
    bundle_id: UUID
    evidence_item_id: UUID
    position: int
    section_label: str | None
    included_reason: str | None


class PrepQuestionCreate(BaseModel):
    issue_id: UUID | None = None
    evidence_item_id: UUID | None = None
    question: str = Field(min_length=3)
    purpose: str | None = None
    question_type: str = "foundation"


class PrepQuestionRead(ORMModel):
    id: UUID
    matter_id: UUID
    witness_id: UUID
    issue_id: UUID | None
    evidence_item_id: UUID | None
    question: str
    purpose: str | None
    question_type: str
    status: WitnessPrepStatus
    source: str
    metadata_json: dict


class EvidenceGraphNode(BaseModel):
    id: str
    type: str
    label: str
    metadata: dict = Field(default_factory=dict)


class EvidenceGraphEdge(BaseModel):
    source: str
    target: str
    type: str
    metadata: dict = Field(default_factory=dict)


class EvidenceGraphRead(BaseModel):
    nodes: list[EvidenceGraphNode]
    edges: list[EvidenceGraphEdge]


class EvidenceDashboard(BaseModel):
    evidence_items: int
    issues: int
    witnesses: int
    open_gaps: int
    contradictions: int
    proposed_exhibits: int
    reviewed_items: int


class IssueEvidenceRef(BaseModel):
    evidence_item_id: str
    title: str
    kind: str
    strength: str
    link_confidence: float
    weight: float
    rationale: str | None = None


class IssueGapRef(BaseModel):
    gap_id: str
    title: str
    severity: str
    suggested_action: str | None = None


class IssueWitnessRef(BaseModel):
    witness_id: str
    name: str
    kind: str
    side: str | None = None
    supports_items: int


class IssueStandingRead(BaseModel):
    """How one issue stands on the evidence recorded so far.

    `support_ratio` is null when nothing has been linked either way — unknown
    rather than unsupported. It describes the file, not the likely outcome.
    """

    issue_id: str
    code: str
    title: str
    burden_side: str | None = None
    priority: int
    support_ratio: float | None = None
    support_weight: float
    contradict_weight: float
    supporting_count: int
    contradicting_count: int
    supporting: list[IssueEvidenceRef] = Field(default_factory=list)
    contradicting: list[IssueEvidenceRef] = Field(default_factory=list)
    open_gaps: list[IssueGapRef] = Field(default_factory=list)
    depends_on_witnesses: list[IssueWitnessRef] = Field(default_factory=list)
    evidence_recorded: bool
