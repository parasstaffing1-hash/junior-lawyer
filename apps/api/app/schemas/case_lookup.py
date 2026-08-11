from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.case_lookup import CaseLookupStatus, CaseSide, CaseSourceKind


class CasePartyData(BaseModel):
    name: str = Field(min_length=1, max_length=400)
    side: CaseSide
    sequence: int = Field(default=1, ge=1)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CaseAdvocateData(BaseModel):
    name: str = Field(min_length=1, max_length=350)
    side: CaseSide
    enrollment_or_reference: str | None = Field(default=None, max_length=160)


class CaseActData(BaseModel):
    act_name: str = Field(min_length=1, max_length=400)
    sections: list[str] = Field(default_factory=list)
    source_text: str | None = None


class CaseHearingData(BaseModel):
    hearing_date: date
    purpose_or_stage: str | None = Field(default=None, max_length=350)
    judge_or_bench: str | None = Field(default=None, max_length=350)
    result_or_note: str | None = None
    source_reference: str | None = Field(default=None, max_length=500)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CaseOrderData(BaseModel):
    order_date: date | None = None
    title: str | None = Field(default=None, max_length=500)
    order_type: str | None = Field(default=None, max_length=180)
    document_url: str | None = None
    source_url: str | None = None
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CaseJudgmentData(BaseModel):
    decision_date: date | None = None
    title: str | None = Field(default=None, max_length=500)
    citation: str | None = Field(default=None, max_length=300)
    document_url: str | None = None
    source_url: str | None = None
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CaseRecordData(BaseModel):
    cnr: str | None = Field(default=None, max_length=40)
    case_type: str | None = Field(default=None, max_length=120)
    case_number: str = Field(min_length=1, max_length=160)
    year: int | None = Field(default=None, ge=1900, le=2200)
    case_title: str | None = Field(default=None, max_length=500)

    court_name: str = Field(min_length=1, max_length=350)
    court_code: str | None = Field(default=None, max_length=100)
    court_number: str | None = Field(default=None, max_length=120)
    court_level: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=160)
    state: str | None = Field(default=None, max_length=160)

    filing_date: date | None = None
    registration_date: date | None = None
    judge: str | None = Field(default=None, max_length=350)
    bench: str | None = Field(default=None, max_length=350)
    status: str | None = Field(default=None, max_length=180)
    case_stage: str | None = Field(default=None, max_length=240)
    previous_hearing_date: date | None = None
    next_hearing_date: date | None = None

    parties: list[CasePartyData] = Field(default_factory=list)
    advocates: list[CaseAdvocateData] = Field(default_factory=list)
    acts: list[CaseActData] = Field(default_factory=list)
    hearing_history: list[CaseHearingData] = Field(default_factory=list)
    orders: list[CaseOrderData] = Field(default_factory=list)
    judgments: list[CaseJudgmentData] = Field(default_factory=list)

    source_kind: CaseSourceKind
    source_name: str = Field(min_length=2, max_length=260)
    source_url: str | None = None
    source_reference: str | None = Field(default=None, max_length=400)
    fetched_at: datetime
    source_updated_at: datetime | None = None


class CaseLookupRequest(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    state: str | None = Field(default=None, max_length=160)
    district: str | None = Field(default=None, max_length=160)
    court: str | None = Field(default=None, max_length=350)
    include_saved: bool = True


class CaseLookupPreferenceUpdate(BaseModel):
    preferred_state: str | None = Field(default=None, max_length=160)
    preferred_district: str | None = Field(default=None, max_length=160)
    preferred_high_court: str | None = Field(default=None, max_length=260)
    preferred_courts_json: list[str] = Field(default_factory=list)
    default_refresh_minutes: int = Field(default=240, ge=15, le=43200)


class CaseLookupPreferenceRead(CaseLookupPreferenceUpdate):
    id: UUID
    organization_id: UUID
    membership_id: UUID
    recent_courts_json: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class CaseCandidateRead(BaseModel):
    id: UUID
    saved_case_id: UUID | None
    source_kind: CaseSourceKind
    case_record: CaseRecordData
    rank_score: int
    exact_match: bool
    requires_user_verification: bool


class CaseLookupResponse(BaseModel):
    run_id: UUID
    status: CaseLookupStatus
    detected_kind: str
    parsed: dict[str, Any]
    message: str | None
    candidates: list[CaseCandidateRead]


class SavedCaseSummaryRead(BaseModel):
    id: UUID
    matter_id: UUID | None
    cnr: str | None
    case_type: str | None
    case_number: str
    year: int | None
    case_title: str | None
    court_name: str
    district: str | None
    state: str | None
    case_status: str | None
    case_stage: str | None
    next_hearing_date: date | None
    source_name: str
    fetched_at: datetime
    stale_after: datetime | None
    model_config = ConfigDict(from_attributes=True)


class SavedCaseDetailRead(BaseModel):
    id: UUID
    matter_id: UUID | None
    record: CaseRecordData
    changes: list[dict[str, Any]] = Field(default_factory=list)
    stale: bool = False


class OfficialCaseImportRequest(BaseModel):
    record: CaseRecordData
    save_case: bool = True


class LinkCaseMatterRequest(BaseModel):
    matter_id: UUID | None = None
    create_workspace: bool = False
