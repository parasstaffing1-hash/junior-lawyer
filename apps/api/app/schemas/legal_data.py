from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.legal_data_ops import (
    AmendmentReviewStatus,
    JurisdictionReleaseStatus,
    LegalDataAlertStatus,
    LegalDataContentKind,
    LegalDataFeedMode,
    LegalDataRunTrigger,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LegalDataFeedCreate(BaseModel):
    source_id: UUID
    connection_id: UUID | None = None
    code: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str = Field(min_length=2, max_length=300)
    jurisdiction: str = Field(default="India", max_length=160)
    state: str | None = Field(default=None, max_length=160)
    content_kind: LegalDataContentKind = LegalDataContentKind.MIXED
    mode: LegalDataFeedMode = LegalDataFeedMode.MANUAL_MANIFEST
    allowed_domains: list[str] = Field(default_factory=list, max_length=50)
    schedule_interval_minutes: int = Field(default=1440, ge=5, le=525600)
    stale_after_hours: int = Field(default=72, ge=1, le=8760)
    import_path: str | None = Field(default=None, max_length=800)
    metadata: dict = Field(default_factory=dict)


class LegalDataFeedUpdate(BaseModel):
    enabled: bool | None = None
    name: str | None = Field(default=None, min_length=2, max_length=300)
    allowed_domains: list[str] | None = Field(default=None, max_length=50)
    schedule_interval_minutes: int | None = Field(default=None, ge=5, le=525600)
    stale_after_hours: int | None = Field(default=None, ge=1, le=8760)
    import_path: str | None = Field(default=None, max_length=800)
    metadata: dict | None = None


class LegalDataFeedRead(ORMModel):
    id: UUID
    organization_id: UUID
    source_id: UUID
    connection_id: UUID | None
    code: str
    name: str
    jurisdiction: str
    state: str | None
    content_kind: str
    mode: str
    enabled: bool
    allowed_domains_json: list
    schedule_interval_minutes: int
    stale_after_hours: int
    import_path: str | None
    cursor_json: dict
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_manifest_sha256: str | None
    next_due_at: datetime | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class LegalDataManifestItem(BaseModel):
    kind: str = Field(pattern=r"^(statute|judgment)$")
    source_url: str = Field(min_length=8, max_length=2000)
    payload: dict
    source_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")


class LegalDataManifest(BaseModel):
    source_label: str | None = Field(default=None, max_length=500)
    manifest_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    items: list[LegalDataManifestItem] = Field(min_length=1, max_length=5000)
    metadata: dict = Field(default_factory=dict)


class IngestionItemRead(ORMModel):
    id: UUID
    run_id: UUID
    position: int
    kind: str
    external_id: str
    source_url: str
    declared_sha256: str | None
    actual_sha256: str
    status: str
    change_kind: str
    resource_type: str | None
    resource_id: UUID | None
    before_sha256: str | None
    after_sha256: str | None
    error_message: str | None
    metadata_json: dict


class IngestionRunRead(ORMModel):
    id: UUID
    organization_id: UUID
    feed_id: UUID
    initiated_by_membership_id: UUID | None
    trigger: str
    status: str
    manifest_sha256: str | None
    source_label: str | None
    started_at: datetime
    finished_at: datetime | None
    items_total: int
    items_succeeded: int
    items_failed: int
    items_unchanged: int
    items_changed: int
    error_message: str | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class IngestionRunDetail(BaseModel):
    run: IngestionRunRead
    items: list[IngestionItemRead]


class IntegrityCheckRead(ORMModel):
    id: UUID
    feed_id: UUID | None
    run_id: UUID | None
    ingestion_item_id: UUID | None
    check_kind: str
    status: str
    source_url: str | None
    expected_value: str | None
    actual_value: str | None
    checked_at: datetime
    details_json: dict


class AmendmentRead(ORMModel):
    id: UUID
    statute_id: UUID
    section_id: UUID | None
    ingestion_item_id: UUID | None
    event_kind: str
    section_number: str | None
    previous_sha256: str | None
    new_sha256: str | None
    effective_date: date | None
    before_json: dict
    after_json: dict
    review_status: str
    detected_at: datetime
    reviewed_at: datetime | None
    reviewed_by_membership_id: UUID | None
    review_note: str | None


class AmendmentReviewRequest(BaseModel):
    status: AmendmentReviewStatus = AmendmentReviewStatus.REVIEWED
    note: str | None = Field(default=None, max_length=4000)


class JurisdictionPackCreate(BaseModel):
    pack_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str = Field(min_length=2, max_length=300)
    jurisdiction: str = Field(default="India", max_length=160)
    state: str | None = Field(default=None, max_length=160)
    languages: list[str] = Field(default_factory=lambda: ["en", "hi"], max_length=20)
    description: str | None = Field(default=None, max_length=8000)
    metadata: dict = Field(default_factory=dict)


class JurisdictionPackRead(ORMModel):
    id: UUID
    organization_id: UUID
    pack_key: str
    name: str
    jurisdiction: str
    state: str | None
    languages_json: list
    status: str
    active_release_version: str | None
    description: str | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class JurisdictionPackSourceInput(BaseModel):
    source_id: UUID
    feed_id: UUID | None = None
    required: bool = True
    maximum_age_hours: int = Field(default=72, ge=1, le=8760)
    metadata: dict = Field(default_factory=dict)


class JurisdictionReleaseCreate(BaseModel):
    version: str = Field(min_length=1, max_length=80)
    effective_from: date | None = None
    effective_to: date | None = None
    notes: str | None = Field(default=None, max_length=8000)
    sources: list[JurisdictionPackSourceInput] = Field(min_length=1, max_length=100)
    metadata: dict = Field(default_factory=dict)


class JurisdictionReleaseRead(ORMModel):
    id: UUID
    pack_id: UUID
    version: str
    status: str
    effective_from: date | None
    effective_to: date | None
    manifest_sha256: str
    notes: str | None
    approved_by_membership_id: UUID | None
    activated_at: datetime | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class JurisdictionReleaseStatusRequest(BaseModel):
    status: JurisdictionReleaseStatus


class LegalDataAlertRead(ORMModel):
    id: UUID
    feed_id: UUID | None
    run_id: UUID | None
    kind: str
    severity: str
    status: str
    dedupe_key: str
    title: str
    message: str
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    metadata_json: dict


class AlertStatusRequest(BaseModel):
    status: LegalDataAlertStatus


class CorpusCheckpointRead(ORMModel):
    id: UUID
    run_id: UUID | None
    statutes: int
    sections: int
    judgments: int
    paragraphs: int
    citations: int
    aggregate_sha256: str
    captured_at: datetime
    metadata_json: dict


class FeedSyncRequest(BaseModel):
    trigger: LegalDataRunTrigger = LegalDataRunTrigger.MANUAL


class LegalDataDashboard(BaseModel):
    feeds: int
    stale_feeds: int
    open_alerts: int
    pending_amendments: int
    runs_24h: int
    failed_runs_24h: int
    active_packs: int
    latest_checkpoint: CorpusCheckpointRead | None
    recent_runs: list[IngestionRunRead]
    alerts: list[LegalDataAlertRead]
