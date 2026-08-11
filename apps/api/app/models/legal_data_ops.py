from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class LegalDataFeedMode(StrEnum):
    MANUAL_MANIFEST = "manual_manifest"
    FILESYSTEM_DROP = "filesystem_drop"
    INTEGRATION_PUSH = "integration_push"


class LegalDataContentKind(StrEnum):
    STATUTE = "statute"
    JUDGMENT = "judgment"
    MIXED = "mixed"


class LegalDataRunTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WORKER = "worker"
    INTEGRATION = "integration"


class LegalDataRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class LegalDataItemStatus(StrEnum):
    PENDING = "pending"
    IMPORTED = "imported"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"
    FAILED = "failed"


class LegalDataChangeKind(StrEnum):
    NEW = "new"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class IntegrityStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class IntegrityCheckKind(StrEnum):
    SOURCE_HOST = "source_host"
    PAYLOAD_HASH = "payload_hash"
    SCHEMA = "schema"
    FRESHNESS = "freshness"
    SOURCE_ENABLED = "source_enabled"
    PACK_SOURCE = "pack_source"


class AmendmentEventKind(StrEnum):
    SECTION_ADDED = "section_added"
    SECTION_CHANGED = "section_changed"
    SECTION_REMOVED_FROM_MANIFEST = "section_removed_from_manifest"
    STATUTE_METADATA_CHANGED = "statute_metadata_changed"


class AmendmentReviewStatus(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class JurisdictionPackStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class JurisdictionReleaseStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    ACTIVE = "active"
    RETIRED = "retired"


class LegalDataAlertKind(StrEnum):
    SOURCE_STALE = "source_stale"
    INTEGRITY_FAILURE = "integrity_failure"
    INGESTION_FAILURE = "ingestion_failure"
    AMENDMENT_DETECTED = "amendment_detected"
    PACK_SOURCE_UNHEALTHY = "pack_source_unhealthy"


class LegalDataAlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class LegalDataAlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class LegalDataFeed(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_data_feeds"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_legal_data_feed_org_code"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("legal_sources.id", ondelete="RESTRICT"), index=True)
    connection_id: Mapped[UUID | None] = mapped_column(ForeignKey("integration_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(300))
    jurisdiction: Mapped[str] = mapped_column(String(160), default="India", index=True)
    state: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    content_kind: Mapped[str] = mapped_column(String(30), default=LegalDataContentKind.MIXED, index=True)
    mode: Mapped[str] = mapped_column(String(40), default=LegalDataFeedMode.MANUAL_MANIFEST, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    allowed_domains_json: Mapped[list] = mapped_column(JSON, default=list)
    schedule_interval_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    stale_after_hours: Mapped[int] = mapped_column(Integer, default=72)
    import_path: Mapped[str | None] = mapped_column(String(800), nullable=True)
    cursor_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class LegalDataIngestionRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_data_ingestion_runs"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    feed_id: Mapped[UUID] = mapped_column(ForeignKey("legal_data_feeds.id", ondelete="CASCADE"), index=True)
    initiated_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True, index=True)
    trigger: Mapped[str] = mapped_column(String(30), default=LegalDataRunTrigger.MANUAL, index=True)
    status: Mapped[str] = mapped_column(String(30), default=LegalDataRunStatus.RUNNING, index=True)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    items_total: Mapped[int] = mapped_column(Integer, default=0)
    items_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, default=0)
    items_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    items_changed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class LegalDataIngestionItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_data_ingestion_items"
    __table_args__ = (UniqueConstraint("run_id", "position", name="uq_legal_data_ingestion_item_position"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("legal_data_ingestion_runs.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    external_id: Mapped[str] = mapped_column(String(300), index=True)
    source_url: Mapped[str] = mapped_column(String(2000))
    declared_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actual_sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default=LegalDataItemStatus.PENDING, index=True)
    change_kind: Mapped[str] = mapped_column(String(30), default=LegalDataChangeKind.UNCHANGED, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    before_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class LegalDataSourceSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_data_source_snapshots"
    __table_args__ = (UniqueConstraint("feed_id", "kind", "external_id", "content_sha256", name="uq_legal_data_source_snapshot_hash"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    feed_id: Mapped[UUID] = mapped_column(ForeignKey("legal_data_feeds.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_data_ingestion_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    external_id: Mapped[str] = mapped_column(String(300), index=True)
    source_url: Mapped[str] = mapped_column(String(2000))
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    previous_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default=IntegrityStatus.PASS, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class LegalDataIntegrityCheck(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_data_integrity_checks"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    feed_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_data_feeds.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_data_ingestion_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    ingestion_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_data_ingestion_items.id", ondelete="SET NULL"), nullable=True, index=True)
    check_kind: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)


class StatuteAmendmentEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "statute_amendment_events"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    statute_id: Mapped[UUID] = mapped_column(ForeignKey("statutes.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[UUID | None] = mapped_column(ForeignKey("statute_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    ingestion_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_data_ingestion_items.id", ondelete="SET NULL"), nullable=True, index=True)
    event_kind: Mapped[str] = mapped_column(String(60), index=True)
    section_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    previous_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    before_json: Mapped[dict] = mapped_column(JSON, default=dict)
    after_json: Mapped[dict] = mapped_column(JSON, default=dict)
    review_status: Mapped[str] = mapped_column(String(30), default=AmendmentReviewStatus.PENDING, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class JurisdictionPack(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "jurisdiction_packs"
    __table_args__ = (UniqueConstraint("organization_id", "pack_key", name="uq_jurisdiction_pack_org_key"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    pack_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(300))
    jurisdiction: Mapped[str] = mapped_column(String(160), index=True)
    state: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    languages_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default=JurisdictionPackStatus.DRAFT, index=True)
    active_release_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class JurisdictionPackRelease(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "jurisdiction_pack_releases"
    __table_args__ = (UniqueConstraint("pack_id", "version", name="uq_jurisdiction_pack_release_version"),)

    pack_id: Mapped[UUID] = mapped_column(ForeignKey("jurisdiction_packs.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default=JurisdictionReleaseStatus.DRAFT, index=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class JurisdictionPackSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "jurisdiction_pack_sources"
    __table_args__ = (UniqueConstraint("release_id", "source_id", "feed_id", name="uq_jurisdiction_pack_release_source"),)

    release_id: Mapped[UUID] = mapped_column(ForeignKey("jurisdiction_pack_releases.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("legal_sources.id", ondelete="RESTRICT"), index=True)
    feed_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_data_feeds.id", ondelete="SET NULL"), nullable=True, index=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    maximum_age_hours: Mapped[int] = mapped_column(Integer, default=72)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class LegalDataAlert(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_data_alerts"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    feed_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_data_feeds.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_data_ingestion_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30), default=LegalDataAlertStatus.OPEN, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(300), index=True)
    title: Mapped[str] = mapped_column(String(500))
    message: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class LegalCorpusCheckpoint(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "legal_corpus_checkpoints"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("legal_data_ingestion_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    statutes: Mapped[int] = mapped_column(Integer, default=0)
    sections: Mapped[int] = mapped_column(Integer, default=0)
    judgments: Mapped[int] = mapped_column(Integer, default=0)
    paragraphs: Mapped[int] = mapped_column(Integer, default=0)
    citations: Mapped[int] = mapped_column(Integer, default=0)
    aggregate_sha256: Mapped[str] = mapped_column(String(64), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
