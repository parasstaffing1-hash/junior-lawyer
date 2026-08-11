from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.search import SearchEntityType


class SearchIndexJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchIndexJobKind(StrEnum):
    FULL = "full"
    ORGANIZATION = "organization"
    MATTER = "matter"
    DOCUMENT = "document"
    CORPUS = "corpus"
    INCREMENTAL = "incremental"


class DuplicateRelationKind(StrEnum):
    EXACT = "exact"
    NEAR = "near"


class DuplicateRelationStatus(StrEnum):
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    IGNORED = "ignored"


class SearchIndexEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "search_index_entries"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_search_index_entry_source_key"),
    )

    # NULL organization means public legal corpus. Firm material always carries its organization.
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    entity_type: Mapped[SearchEntityType] = mapped_column(String(40), index=True)
    entity_id: Mapped[UUID] = mapped_column(index=True)
    chunk_key: Mapped[str] = mapped_column(String(220), default="root")
    source_key: Mapped[str] = mapped_column(String(700), index=True)

    matter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=True, index=True
    )
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(700), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(1000))
    body_text: Mapped[str] = mapped_column(Text, default="")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    href: Mapped[str] = mapped_column(String(1200))
    badges_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    simhash64: Mapped[str] = mapped_column(String(16), index=True)
    feature_vector_json: Mapped[list] = mapped_column(JSON, default=list)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    rank_weight: Mapped[float] = mapped_column(Float, default=1.0)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class SearchIndexJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "search_index_jobs"

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    requested_by_membership_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[SearchIndexJobKind] = mapped_column(String(30), index=True)
    status: Mapped[SearchIndexJobStatus] = mapped_column(String(30), default=SearchIndexJobStatus.PENDING, index=True)
    scope_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    entries_seen: Mapped[int] = mapped_column(Integer, default=0)
    entries_created: Mapped[int] = mapped_column(Integer, default=0)
    entries_updated: Mapped[int] = mapped_column(Integer, default=0)
    entries_deleted: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_detected: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SearchIndexCursor(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "search_index_cursors"
    __table_args__ = (
        UniqueConstraint("organization_id", "source_name", name="uq_search_index_cursor_org_source"),
    )

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_name: Mapped[str] = mapped_column(String(120), index=True)
    last_source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_entity_id: Mapped[UUID | None] = mapped_column(nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SearchDuplicateRelation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "search_duplicate_relations"
    __table_args__ = (
        UniqueConstraint("left_entry_id", "right_entry_id", name="uq_search_duplicate_pair"),
    )

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    left_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("search_index_entries.id", ondelete="CASCADE"), index=True
    )
    right_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("search_index_entries.id", ondelete="CASCADE"), index=True
    )
    relation_kind: Mapped[DuplicateRelationKind] = mapped_column(String(20), index=True)
    status: Mapped[DuplicateRelationStatus] = mapped_column(String(20), default=DuplicateRelationStatus.DETECTED, index=True)
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    hamming_distance: Mapped[int] = mapped_column(Integer, default=64)
    shingle_jaccard: Mapped[float] = mapped_column(Float, default=0.0)
    reviewed_by_membership_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SearchIndexHealthSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "search_index_health_snapshots"

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    stale_count: Mapped[int] = mapped_column(Integer, default=0)
    exact_duplicate_pairs: Mapped[int] = mapped_column(Integer, default=0)
    near_duplicate_pairs: Mapped[int] = mapped_column(Integer, default=0)
    by_entity_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_completed_job_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)


class SearchPerformancePreference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "search_performance_preferences"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_search_performance_preferences_org"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    use_index: Mapped[bool] = mapped_column(Boolean, default=True)
    lexical_weight: Mapped[float] = mapped_column(Float, default=0.72)
    feature_vector_weight: Mapped[float] = mapped_column(Float, default=0.18)
    exact_title_weight: Mapped[float] = mapped_column(Float, default=0.07)
    type_weight: Mapped[float] = mapped_column(Float, default=0.03)
    near_duplicate_hamming: Mapped[int] = mapped_column(Integer, default=6)
    near_duplicate_jaccard: Mapped[float] = mapped_column(Float, default=0.82)
    max_candidate_rows: Mapped[int] = mapped_column(Integer, default=400)
    local_embedding_mode: Mapped[str] = mapped_column(String(40), default="feature_hash")
