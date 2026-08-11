from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.contract import ContractRiskLevel, ContractRiskProfile, ContractType


class ReviewSourceFormat(StrEnum):
    DOCX = "docx"
    PDF = "pdf"
    TXT = "txt"


class ContractReviewStatus(StrEnum):
    UPLOADED = "uploaded"
    ANALYZED = "analyzed"
    IN_NEGOTIATION = "in_negotiation"
    APPROVED = "approved"
    ARCHIVED = "archived"


class ClauseDeviationStatus(StrEnum):
    MATCHED = "matched"
    MODIFIED = "modified"
    UNKNOWN = "unknown"


class ReviewFindingStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"
    IGNORED = "ignored"


class PlaybookRequirement(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    PROHIBITED = "prohibited"


class RedlineStatus(StrEnum):
    GENERATED = "generated"
    SUPERSEDED = "superseded"


class ContractPlaybook(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contract_playbooks"
    __table_args__ = (UniqueConstraint("organization_id", "name", "contract_type", name="uq_contract_playbook_org_name_type"),)

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(240), index=True)
    owner_label: Mapped[str] = mapped_column(String(240), default="Default India Playbook")
    contract_type: Mapped[ContractType] = mapped_column(Enum(ContractType, native_enum=False), index=True)
    risk_profile: Mapped[ContractRiskProfile] = mapped_column(
        Enum(ContractRiskProfile, native_enum=False), default=ContractRiskProfile.BALANCED, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)

    rules = relationship(
        "ContractPlaybookRule", back_populates="playbook", cascade="all, delete-orphan", lazy="selectin"
    )
    reviews = relationship("CounterpartyContractReview", back_populates="playbook")


class ContractPlaybookRule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contract_playbook_rules"
    __table_args__ = (UniqueConstraint("playbook_id", "code", name="uq_contract_playbook_rule_code"),)

    playbook_id: Mapped[UUID] = mapped_column(ForeignKey("contract_playbooks.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(180), index=True)
    clause_type: Mapped[str] = mapped_column(String(120), index=True)
    requirement: Mapped[PlaybookRequirement] = mapped_column(
        Enum(PlaybookRequirement, native_enum=False), default=PlaybookRequirement.REQUIRED, index=True
    )
    preferred_variant: Mapped[str] = mapped_column(String(80), default="balanced")
    risk_level: Mapped[ContractRiskLevel] = mapped_column(Enum(ContractRiskLevel, native_enum=False), index=True)
    guidance_en: Mapped[str] = mapped_column(Text, default="")
    guidance_hi: Mapped[str | None] = mapped_column(Text)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)

    playbook = relationship("ContractPlaybook", back_populates="rules")


class CounterpartyContractReview(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "counterparty_contract_reviews"

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    internal_contract_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    playbook_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contract_playbooks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(350), index=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(300), index=True)
    contract_type: Mapped[ContractType] = mapped_column(Enum(ContractType, native_enum=False), index=True)
    status: Mapped[ContractReviewStatus] = mapped_column(
        Enum(ContractReviewStatus, native_enum=False), default=ContractReviewStatus.UPLOADED, index=True
    )
    source_format: Mapped[ReviewSourceFormat] = mapped_column(Enum(ReviewSourceFormat, native_enum=False), index=True)
    source_filename: Mapped[str] = mapped_column(String(350))
    source_storage_key: Mapped[str] = mapped_column(String(900))
    source_sha256: Mapped[str] = mapped_column(String(64), index=True)
    language: Mapped[str] = mapped_column(String(30), default="unknown", index=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    text_length: Mapped[int] = mapped_column(Integer, default=0)
    health_score: Mapped[int] = mapped_column(Integer, default=100)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    playbook = relationship("ContractPlaybook", back_populates="reviews", lazy="selectin")
    clauses = relationship(
        "CounterpartyReviewClause", back_populates="review", cascade="all, delete-orphan",
        lazy="selectin", order_by="CounterpartyReviewClause.position"
    )
    findings = relationship(
        "CounterpartyReviewFinding", back_populates="review", cascade="all, delete-orphan",
        lazy="selectin", order_by="CounterpartyReviewFinding.created_at"
    )
    redlines = relationship(
        "ContractRedlineVersion", back_populates="review", cascade="all, delete-orphan",
        lazy="selectin", order_by="ContractRedlineVersion.version_number"
    )


class CounterpartyReviewClause(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "counterparty_review_clauses"
    __table_args__ = (UniqueConstraint("review_id", "position", name="uq_counterparty_review_clause_position"),)

    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("counterparty_contract_reviews.id", ondelete="CASCADE"), index=True
    )
    clause_type: Mapped[str] = mapped_column(String(120), index=True)
    heading: Mapped[str | None] = mapped_column(String(350))
    source_text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, index=True)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    matched_template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clause_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    deviation_status: Mapped[ClauseDeviationStatus] = mapped_column(
        Enum(ClauseDeviationStatus, native_enum=False), default=ClauseDeviationStatus.UNKNOWN, index=True
    )
    suggested_title_en: Mapped[str | None] = mapped_column(String(300))
    suggested_title_hi: Mapped[str | None] = mapped_column(String(300))
    suggested_body_en: Mapped[str | None] = mapped_column(Text)
    suggested_body_hi: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str | None] = mapped_column(String(80), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    review = relationship("CounterpartyContractReview", back_populates="clauses")
    matched_template = relationship("ClauseTemplate")
    findings = relationship("CounterpartyReviewFinding", back_populates="clause", lazy="selectin")


class CounterpartyReviewFinding(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "counterparty_review_findings"
    __table_args__ = (UniqueConstraint("review_id", "rule_code", name="uq_counterparty_review_finding_rule"),)

    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("counterparty_contract_reviews.id", ondelete="CASCADE"), index=True
    )
    review_clause_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("counterparty_review_clauses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(220), index=True)
    clause_type: Mapped[str | None] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(350))
    explanation: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text, default="Review with counsel")
    level: Mapped[ContractRiskLevel] = mapped_column(Enum(ContractRiskLevel, native_enum=False), index=True)
    status: Mapped[ReviewFindingStatus] = mapped_column(
        Enum(ReviewFindingStatus, native_enum=False), default=ReviewFindingStatus.OPEN, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    review = relationship("CounterpartyContractReview", back_populates="findings")
    clause = relationship("CounterpartyReviewClause", back_populates="findings")


class ContractRedlineVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contract_redline_versions"
    __table_args__ = (UniqueConstraint("review_id", "version_number", name="uq_contract_redline_version"),)

    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("counterparty_contract_reviews.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String(180), default="Negotiation redline")
    status: Mapped[RedlineStatus] = mapped_column(
        Enum(RedlineStatus, native_enum=False), default=RedlineStatus.GENERATED, index=True
    )
    changes_json: Mapped[list] = mapped_column(JSON, default=list)
    generated_filename: Mapped[str] = mapped_column(String(350))
    generated_storage_key: Mapped[str] = mapped_column(String(900))
    sha256: Mapped[str] = mapped_column(String(64), index=True)

    review = relationship("CounterpartyContractReview", back_populates="redlines")
