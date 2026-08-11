from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ContractType(StrEnum):
    NDA = "nda"
    EMPLOYMENT = "employment"
    CONSULTING = "consulting"
    FREELANCE = "freelance"
    VENDOR = "vendor"
    SERVICES = "services"
    SAAS = "saas"
    SOFTWARE_DEVELOPMENT = "software_development"


class ContractLanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    BILINGUAL = "bilingual"


class ContractStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class ContractRiskProfile(StrEnum):
    BALANCED = "balanced"
    PRO_PARTY_A = "pro_party_a"
    PRO_PARTY_B = "pro_party_b"


class ContractRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContractRiskStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class ClauseSource(StrEnum):
    BUILTIN = "builtin"
    CUSTOM = "custom"


class Contract(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contracts"

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    matter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(350), index=True)
    contract_type: Mapped[ContractType] = mapped_column(
        Enum(ContractType, native_enum=False), index=True
    )
    language: Mapped[ContractLanguage] = mapped_column(
        Enum(ContractLanguage, native_enum=False), default=ContractLanguage.ENGLISH, index=True
    )
    status: Mapped[ContractStatus] = mapped_column(
        Enum(ContractStatus, native_enum=False), default=ContractStatus.DRAFT, index=True
    )
    risk_profile: Mapped[ContractRiskProfile] = mapped_column(
        Enum(ContractRiskProfile, native_enum=False), default=ContractRiskProfile.BALANCED, index=True
    )
    jurisdiction: Mapped[str] = mapped_column(String(120), default="India", index=True)
    governing_state: Mapped[str | None] = mapped_column(String(120), index=True)
    party_a_name: Mapped[str] = mapped_column(String(300), index=True)
    party_b_name: Mapped[str] = mapped_column(String(300), index=True)
    effective_date: Mapped[date | None] = mapped_column(Date, index=True)
    questionnaire_json: Mapped[dict] = mapped_column(JSON, default=dict)
    health_score: Mapped[int] = mapped_column(Integer, default=100)
    generated_filename: Mapped[str | None] = mapped_column(String(350))
    generated_storage_key: Mapped[str | None] = mapped_column(String(900))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    matter = relationship("Matter", back_populates="contracts")
    clauses = relationship(
        "ContractClause",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ContractClause.position",
    )
    risks = relationship(
        "ContractRisk",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ContractRisk.created_at",
    )
    versions = relationship(
        "ContractVersion",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ContractVersion.version_number",
    )


class ClauseTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "clause_templates"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_clause_templates_code_version"),
    )

    code: Mapped[str] = mapped_column(String(180), index=True)
    clause_type: Mapped[str] = mapped_column(String(120), index=True)
    variant_key: Mapped[str] = mapped_column(String(80), default="balanced", index=True)
    title_en: Mapped[str] = mapped_column(String(300))
    title_hi: Mapped[str | None] = mapped_column(String(300))
    body_en: Mapped[str] = mapped_column(Text)
    body_hi: Mapped[str | None] = mapped_column(Text)
    contract_types_json: Mapped[list] = mapped_column(JSON, default=list)
    variables_json: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    contract_clauses = relationship("ContractClause", back_populates="template")


class ContractClause(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contract_clauses"
    __table_args__ = (
        UniqueConstraint("contract_id", "position", name="uq_contract_clauses_position"),
    )

    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    clause_template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clause_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    clause_code: Mapped[str] = mapped_column(String(180), index=True)
    clause_type: Mapped[str] = mapped_column(String(120), index=True)
    variant_key: Mapped[str] = mapped_column(String(80), default="balanced", index=True)
    title_en: Mapped[str] = mapped_column(String(300))
    title_hi: Mapped[str | None] = mapped_column(String(300))
    body_en: Mapped[str] = mapped_column(Text)
    body_hi: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[ClauseSource] = mapped_column(
        Enum(ClauseSource, native_enum=False), default=ClauseSource.BUILTIN, index=True
    )
    is_modified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    contract = relationship("Contract", back_populates="clauses")
    template = relationship("ClauseTemplate", back_populates="contract_clauses")


class ContractRisk(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contract_risks"
    __table_args__ = (
        UniqueConstraint("contract_id", "rule_code", name="uq_contract_risks_rule"),
    )

    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    rule_code: Mapped[str] = mapped_column(String(180), index=True)
    clause_type: Mapped[str | None] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(320))
    explanation: Mapped[str] = mapped_column(Text)
    level: Mapped[ContractRiskLevel] = mapped_column(
        Enum(ContractRiskLevel, native_enum=False), index=True
    )
    status: Mapped[ContractRiskStatus] = mapped_column(
        Enum(ContractRiskStatus, native_enum=False), default=ContractRiskStatus.OPEN, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    contract = relationship("Contract", back_populates="risks")


class ContractVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contract_versions"
    __table_args__ = (
        UniqueConstraint("contract_id", "version_number", name="uq_contract_versions_number"),
    )

    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String(180), default="Draft")
    questionnaire_json: Mapped[dict] = mapped_column(JSON, default=dict)
    clauses_json: Mapped[list] = mapped_column(JSON, default=list)
    risks_json: Mapped[list] = mapped_column(JSON, default=list)
    health_score: Mapped[int] = mapped_column(Integer, default=100)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    generated_filename: Mapped[str | None] = mapped_column(String(350))
    generated_storage_key: Mapped[str | None] = mapped_column(String(900))

    contract = relationship("Contract", back_populates="versions")
