from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class KnowledgeAssetKind(StrEnum):
    PLEADING_SECTION = "pleading_section"
    CONTRACT_CLAUSE = "contract_clause"
    ARGUMENT = "argument"
    RESEARCH_MEMO = "research_memo"
    AUTHORITY_NOTE = "authority_note"
    CHECKLIST = "checklist"
    TEMPLATE = "template"
    PRACTICE_NOTE = "practice_note"


class KnowledgeAssetStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    RETIRED = "retired"


class KnowledgeLanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    BILINGUAL = "bilingual"


class SanitizationStatus(StrEnum):
    NOT_REVIEWED = "not_reviewed"
    REVIEWED = "reviewed"
    NOT_REQUIRED = "not_required"


class KnowledgeSourceType(StrEnum):
    MATTER = "matter"
    DOCUMENT = "document"
    DRAFT = "draft"
    DRAFT_SECTION = "draft_section"
    CONTRACT = "contract"
    CONTRACT_CLAUSE = "contract_clause"
    JUDGMENT = "judgment"
    JUDGMENT_PARAGRAPH = "judgment_paragraph"
    STATUTE_SECTION = "statute_section"
    MANUAL = "manual"


class KnowledgeAnnotationKind(StrEnum):
    NOTE = "note"
    WARNING = "warning"
    TIP = "tip"
    OUTCOME = "outcome"


class KnowledgeCollectionStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MatterPlaybookStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


class ResearchCollectionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


class KnowledgeCollection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_collections"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_knowledge_collection_org_name"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(260), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[KnowledgeCollectionStatus] = mapped_column(Enum(KnowledgeCollectionStatus, native_enum=False), default=KnowledgeCollectionStatus.ACTIVE, index=True)
    practice_area: Mapped[str | None] = mapped_column(String(180), index=True)
    created_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class KnowledgeAsset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_assets"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_collections.id", ondelete="SET NULL"), nullable=True, index=True)
    source_matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(450), index=True)
    kind: Mapped[KnowledgeAssetKind] = mapped_column(Enum(KnowledgeAssetKind, native_enum=False), index=True)
    language: Mapped[KnowledgeLanguage] = mapped_column(Enum(KnowledgeLanguage, native_enum=False), default=KnowledgeLanguage.ENGLISH, index=True)
    status: Mapped[KnowledgeAssetStatus] = mapped_column(Enum(KnowledgeAssetStatus, native_enum=False), default=KnowledgeAssetStatus.DRAFT, index=True)
    sanitization_status: Mapped[SanitizationStatus] = mapped_column(Enum(SanitizationStatus, native_enum=False), default=SanitizationStatus.NOT_REVIEWED, index=True)
    body_en: Mapped[str | None] = mapped_column(Text)
    body_hi: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    jurisdiction: Mapped[str | None] = mapped_column(String(160), index=True)
    practice_area: Mapped[str | None] = mapped_column(String(180), index=True)
    matter_type: Mapped[str | None] = mapped_column(String(180), index=True)
    outcome_label: Mapped[str | None] = mapped_column(String(120), index=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    search_text: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class KnowledgeAssetSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_asset_sources"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_assets.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[KnowledgeSourceType] = mapped_column(Enum(KnowledgeSourceType, native_enum=False), index=True)
    source_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    source_matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    label: Mapped[str] = mapped_column(String(500))
    locator: Mapped[str | None] = mapped_column(String(300))
    excerpt: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class KnowledgeAssetVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_asset_versions"
    __table_args__ = (UniqueConstraint("asset_id", "version_number", name="uq_knowledge_asset_version_number"),)

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_assets.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, index=True)
    label: Mapped[str] = mapped_column(String(180), default="Snapshot")
    title: Mapped[str] = mapped_column(String(450))
    body_en: Mapped[str | None] = mapped_column(Text)
    body_hi: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class KnowledgeTag(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_tags"
    __table_args__ = (UniqueConstraint("organization_id", "normalized_name", name="uq_knowledge_tag_org_name"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    normalized_name: Mapped[str] = mapped_column(String(160), index=True)
    display_name: Mapped[str] = mapped_column(String(180))
    language: Mapped[KnowledgeLanguage] = mapped_column(Enum(KnowledgeLanguage, native_enum=False), default=KnowledgeLanguage.ENGLISH, index=True)


class KnowledgeAssetTag(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_asset_tags"
    __table_args__ = (UniqueConstraint("asset_id", "tag_id", name="uq_knowledge_asset_tag"),)

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_assets.id", ondelete="CASCADE"), index=True)
    tag_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_tags.id", ondelete="CASCADE"), index=True)


class KnowledgeAnnotation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_annotations"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_assets.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[KnowledgeAnnotationKind] = mapped_column(Enum(KnowledgeAnnotationKind, native_enum=False), default=KnowledgeAnnotationKind.NOTE, index=True)
    body: Mapped[str] = mapped_column(Text)
    anchor_json: Mapped[dict] = mapped_column(JSON, default=dict)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class MatterPlaybook(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_playbooks"
    __table_args__ = (UniqueConstraint("organization_id", "code", "version", name="uq_matter_playbook_org_code_version"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(160), index=True)
    name_en: Mapped[str] = mapped_column(String(300))
    name_hi: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    practice_area: Mapped[str | None] = mapped_column(String(180), index=True)
    matter_type: Mapped[str | None] = mapped_column(String(180), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, index=True)
    status: Mapped[MatterPlaybookStatus] = mapped_column(Enum(MatterPlaybookStatus, native_enum=False), default=MatterPlaybookStatus.DRAFT, index=True)
    created_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class MatterPlaybookItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_playbook_items"
    __table_args__ = (UniqueConstraint("playbook_id", "position", name="uq_matter_playbook_item_position"),)

    playbook_id: Mapped[UUID] = mapped_column(ForeignKey("matter_playbooks.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    step_code: Mapped[str] = mapped_column(String(160), index=True)
    title_en: Mapped[str] = mapped_column(String(350))
    title_hi: Mapped[str | None] = mapped_column(String(350))
    stage: Mapped[str | None] = mapped_column(String(160), index=True)
    position: Mapped[int] = mapped_column(Integer, index=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    instructions: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ResearchCollection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "research_collections"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_research_collection_org_name"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(350), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    practice_area: Mapped[str | None] = mapped_column(String(180), index=True)
    issue_key: Mapped[str | None] = mapped_column(String(180), index=True)
    status: Mapped[ResearchCollectionStatus] = mapped_column(Enum(ResearchCollectionStatus, native_enum=False), default=ResearchCollectionStatus.DRAFT, index=True)
    created_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ResearchCollectionItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "research_collection_items"
    __table_args__ = (UniqueConstraint("collection_id", "position", name="uq_research_collection_item_position"),)

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("research_collections.id", ondelete="CASCADE"), index=True)
    judgment_id: Mapped[UUID] = mapped_column(ForeignKey("judgments.id", ondelete="CASCADE"), index=True)
    paragraph_id: Mapped[UUID | None] = mapped_column(ForeignKey("judgment_paragraphs.id", ondelete="SET NULL"), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, index=True)
    proposition: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
