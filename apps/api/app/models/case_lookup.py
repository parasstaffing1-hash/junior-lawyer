from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class CaseSide(StrEnum):
    PETITIONER = "petitioner"
    RESPONDENT = "respondent"


class CaseSourceKind(StrEnum):
    SAVED = "saved"
    DISTRICT_COURT = "district_court"
    HIGH_COURT = "high_court"
    SUPREME_COURT = "supreme_court"
    OFFICIAL_IMPORT = "official_import"
    USER_ASSISTED = "user_assisted"


class CaseLookupStatus(StrEnum):
    PENDING = "pending"
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    USER_VERIFICATION_REQUIRED = "user_verification_required"
    FAILED = "failed"


class CaseRecordStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class CaseChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


class CaseLookupPreference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "case_lookup_preferences"
    __table_args__ = (UniqueConstraint("membership_id", name="uq_case_lookup_preference_membership"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    preferred_state: Mapped[str | None] = mapped_column(String(160), index=True)
    preferred_district: Mapped[str | None] = mapped_column(String(160), index=True)
    preferred_high_court: Mapped[str | None] = mapped_column(String(260), index=True)
    preferred_courts_json: Mapped[list] = mapped_column(JSON, default=list)
    recent_courts_json: Mapped[list] = mapped_column(JSON, default=list)
    default_refresh_minutes: Mapped[int] = mapped_column(Integer, default=240)


class SavedCase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_cases"
    __table_args__ = (
        UniqueConstraint("organization_id", "cnr", name="uq_saved_case_org_cnr"),
        UniqueConstraint("organization_id", "source_case_key", name="uq_saved_case_org_source_key"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[UUID | None] = mapped_column(ForeignKey("matters.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    current_snapshot_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)

    cnr: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    source_case_key: Mapped[str] = mapped_column(String(300), index=True)
    case_type: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    case_number: Mapped[str] = mapped_column(String(160), index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    case_title: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)

    court_name: Mapped[str] = mapped_column(String(350), index=True)
    court_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    court_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    court_level: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    district: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)

    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    judge: Mapped[str | None] = mapped_column(String(350), nullable=True)
    bench: Mapped[str | None] = mapped_column(String(350), nullable=True)
    case_status: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    case_stage: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    previous_hearing_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    next_hearing_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    source_kind: Mapped[CaseSourceKind] = mapped_column(Enum(CaseSourceKind, native_enum=False), index=True)
    source_name: Mapped[str] = mapped_column(String(260))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(400), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stale_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    record_status: Mapped[CaseRecordStatus] = mapped_column(Enum(CaseRecordStatus, native_enum=False), default=CaseRecordStatus.ACTIVE, index=True)


class SavedCaseParty(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_case_parties"
    saved_case_id: Mapped[UUID] = mapped_column(ForeignKey("saved_cases.id", ondelete="CASCADE"), index=True)
    side: Mapped[CaseSide] = mapped_column(Enum(CaseSide, native_enum=False), index=True)
    name: Mapped[str] = mapped_column(String(400), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SavedCaseAdvocate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_case_advocates"
    saved_case_id: Mapped[UUID] = mapped_column(ForeignKey("saved_cases.id", ondelete="CASCADE"), index=True)
    side: Mapped[CaseSide] = mapped_column(Enum(CaseSide, native_enum=False), index=True)
    name: Mapped[str] = mapped_column(String(350), index=True)
    enrollment_or_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)


class SavedCaseAct(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_case_acts"
    saved_case_id: Mapped[UUID] = mapped_column(ForeignKey("saved_cases.id", ondelete="CASCADE"), index=True)
    act_name: Mapped[str] = mapped_column(String(400), index=True)
    sections_json: Mapped[list] = mapped_column(JSON, default=list)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class SavedCaseHearing(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_case_hearings"
    saved_case_id: Mapped[UUID] = mapped_column(ForeignKey("saved_cases.id", ondelete="CASCADE"), index=True)
    hearing_date: Mapped[date] = mapped_column(Date, index=True)
    purpose_or_stage: Mapped[str | None] = mapped_column(String(350), nullable=True)
    judge_or_bench: Mapped[str | None] = mapped_column(String(350), nullable=True)
    result_or_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SavedCaseOrder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_case_orders"
    saved_case_id: Mapped[UUID] = mapped_column(ForeignKey("saved_cases.id", ondelete="CASCADE"), index=True)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SavedCaseJudgment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "saved_case_judgments"
    saved_case_id: Mapped[UUID] = mapped_column(ForeignKey("saved_cases.id", ondelete="CASCADE"), index=True)
    decision_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    citation: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class CaseSourceSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "case_source_snapshots"
    saved_case_id: Mapped[UUID] = mapped_column(ForeignKey("saved_cases.id", ondelete="CASCADE"), index=True)
    source_kind: Mapped[CaseSourceKind] = mapped_column(Enum(CaseSourceKind, native_enum=False), index=True)
    source_name: Mapped[str] = mapped_column(String(260))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)


class CaseSnapshotChange(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "case_snapshot_changes"
    saved_case_id: Mapped[UUID] = mapped_column(ForeignKey("saved_cases.id", ondelete="CASCADE"), index=True)
    previous_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("case_source_snapshots.id", ondelete="SET NULL"), nullable=True)
    current_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("case_source_snapshots.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(160), index=True)
    change_type: Mapped[CaseChangeType] = mapped_column(Enum(CaseChangeType, native_enum=False), index=True)
    old_value_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    new_value_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str] = mapped_column(String(700))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)


class CaseLookupRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "case_lookup_runs"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), nullable=True)
    raw_query: Mapped[str] = mapped_column(String(300), index=True)
    detected_kind: Mapped[str] = mapped_column(String(80), index=True)
    parsed_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source_kinds_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[CaseLookupStatus] = mapped_column(Enum(CaseLookupStatus, native_enum=False), index=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class CaseLookupCandidate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "case_lookup_candidates"
    lookup_run_id: Mapped[UUID] = mapped_column(ForeignKey("case_lookup_runs.id", ondelete="CASCADE"), index=True)
    saved_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("saved_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    source_kind: Mapped[CaseSourceKind] = mapped_column(Enum(CaseSourceKind, native_enum=False), index=True)
    case_record_json: Mapped[dict] = mapped_column(JSON, default=dict)
    rank_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    exact_match: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    requires_user_verification: Mapped[bool] = mapped_column(Boolean, default=False)
