from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_lookup import (
    CaseChangeType,
    CaseLookupCandidate,
    CaseLookupPreference,
    CaseLookupRun,
    CaseLookupStatus,
    CaseSide,
    CaseSnapshotChange,
    CaseSourceKind,
    CaseSourceSnapshot,
    SavedCase,
    SavedCaseAct,
    SavedCaseAdvocate,
    SavedCaseHearing,
    SavedCaseJudgment,
    SavedCaseOrder,
    SavedCaseParty,
)
from app.models.matter import Matter, MatterLanguage
from app.schemas.case_lookup import CaseLookupPreferenceUpdate, CaseLookupRequest, CaseRecordData
from app.services.case_lookup.parser import parse_case_query, rank_case_record
from app.services.case_lookup.providers import DISTRICT_COURT_SOURCE, HIGH_COURT_SOURCE, SUPREME_COURT_SOURCE
from app.services.security.context import ActorContext
from app.services.security.permissions import MatterAccessLevel, enforce_current_matter_access


MATERIAL_CHANGE_FIELDS = (
    "case_title", "court_name", "judge", "bench", "status", "case_stage",
    "previous_hearing_date", "next_hearing_date", "parties", "advocates", "acts",
    "hearing_history", "orders", "judgments",
)


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def source_case_key(record: CaseRecordData) -> str:
    if record.cnr:
        return f"cnr:{record.cnr.upper()}"
    return "|".join([
        str(record.source_kind.value),
        (record.court_code or record.court_name).casefold(),
        (record.case_type or "").casefold(),
        str(record.case_number).casefold(),
        str(record.year or ""),
    ])[:300]


async def get_preferences(db: AsyncSession, actor: ActorContext) -> CaseLookupPreference:
    row = await db.scalar(select(CaseLookupPreference).where(CaseLookupPreference.membership_id == actor.membership_id))
    if row:
        return row
    row = CaseLookupPreference(
        organization_id=actor.organization_id,
        membership_id=actor.membership_id,
        preferred_courts_json=[],
        recent_courts_json=[],
        default_refresh_minutes=240,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_preferences(db: AsyncSession, actor: ActorContext, payload: CaseLookupPreferenceUpdate) -> CaseLookupPreference:
    row = await get_preferences(db, actor)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


async def _child_rows(db: AsyncSession, saved_case_id: UUID):
    parties = list((await db.scalars(select(SavedCaseParty).where(SavedCaseParty.saved_case_id == saved_case_id).order_by(SavedCaseParty.side, SavedCaseParty.sequence))).all())
    advocates = list((await db.scalars(select(SavedCaseAdvocate).where(SavedCaseAdvocate.saved_case_id == saved_case_id).order_by(SavedCaseAdvocate.side, SavedCaseAdvocate.name))).all())
    acts = list((await db.scalars(select(SavedCaseAct).where(SavedCaseAct.saved_case_id == saved_case_id).order_by(SavedCaseAct.act_name))).all())
    hearings = list((await db.scalars(select(SavedCaseHearing).where(SavedCaseHearing.saved_case_id == saved_case_id).order_by(SavedCaseHearing.hearing_date))).all())
    orders = list((await db.scalars(select(SavedCaseOrder).where(SavedCaseOrder.saved_case_id == saved_case_id).order_by(SavedCaseOrder.order_date))).all())
    judgments = list((await db.scalars(select(SavedCaseJudgment).where(SavedCaseJudgment.saved_case_id == saved_case_id).order_by(SavedCaseJudgment.decision_date))).all())
    return parties, advocates, acts, hearings, orders, judgments


async def record_from_saved(db: AsyncSession, row: SavedCase) -> dict:
    parties, advocates, acts, hearings, orders, judgments = await _child_rows(db, row.id)
    return {
        "cnr": row.cnr,
        "case_type": row.case_type,
        "case_number": row.case_number,
        "year": row.year,
        "case_title": row.case_title,
        "court_name": row.court_name,
        "court_code": row.court_code,
        "court_number": row.court_number,
        "court_level": row.court_level,
        "district": row.district,
        "state": row.state,
        "filing_date": row.filing_date,
        "registration_date": row.registration_date,
        "judge": row.judge,
        "bench": row.bench,
        "status": row.case_status,
        "case_stage": row.case_stage,
        "previous_hearing_date": row.previous_hearing_date,
        "next_hearing_date": row.next_hearing_date,
        "parties": [{"name": p.name, "side": p.side.value if hasattr(p.side, "value") else p.side, "sequence": p.sequence, "metadata_json": p.metadata_json} for p in parties],
        "advocates": [{"name": a.name, "side": a.side.value if hasattr(a.side, "value") else a.side, "enrollment_or_reference": a.enrollment_or_reference} for a in advocates],
        "acts": [{"act_name": a.act_name, "sections": a.sections_json, "source_text": a.source_text} for a in acts],
        "hearing_history": [{"hearing_date": h.hearing_date, "purpose_or_stage": h.purpose_or_stage, "judge_or_bench": h.judge_or_bench, "result_or_note": h.result_or_note, "source_reference": h.source_reference, "metadata_json": h.metadata_json} for h in hearings],
        "orders": [{"order_date": o.order_date, "title": o.title, "order_type": o.order_type, "document_url": o.document_url, "source_url": o.source_url, "checksum_sha256": o.checksum_sha256, "metadata_json": o.metadata_json} for o in orders],
        "judgments": [{"decision_date": j.decision_date, "title": j.title, "citation": j.citation, "document_url": j.document_url, "source_url": j.source_url, "checksum_sha256": j.checksum_sha256, "metadata_json": j.metadata_json} for j in judgments],
        "source_kind": row.source_kind.value if hasattr(row.source_kind, "value") else row.source_kind,
        "source_name": row.source_name,
        "source_url": row.source_url,
        "source_reference": row.source_reference,
        "fetched_at": row.fetched_at,
        "source_updated_at": row.source_updated_at,
    }


async def search_cases(db: AsyncSession, actor: ActorContext, payload: CaseLookupRequest) -> tuple[CaseLookupRun, list[CaseLookupCandidate]]:
    parsed = parse_case_query(payload.query)
    preferences = await get_preferences(db, actor)
    state = payload.state or preferences.preferred_state
    district = payload.district or preferences.preferred_district
    court = payload.court

    run = CaseLookupRun(
        organization_id=actor.organization_id,
        membership_id=actor.membership_id,
        raw_query=payload.query,
        detected_kind=parsed.kind,
        parsed_json=parsed.as_dict(),
        source_kinds_json=["saved", "district_court", "high_court", "supreme_court"],
        status=CaseLookupStatus.PENDING,
        result_count=0,
    )
    db.add(run)
    await db.flush()

    stmt = select(SavedCase).where(SavedCase.organization_id == actor.organization_id)
    if parsed.cnr:
        stmt = stmt.where(SavedCase.cnr == parsed.cnr)
    elif parsed.case_number:
        stmt = stmt.where(SavedCase.case_number == parsed.case_number)
        if parsed.year:
            stmt = stmt.where(SavedCase.year == parsed.year)
        if parsed.case_type:
            stmt = stmt.where(SavedCase.case_type.ilike(parsed.case_type))
    else:
        like = f"%{payload.query}%"
        stmt = stmt.where(or_(SavedCase.case_title.ilike(like), SavedCase.case_number.ilike(like), SavedCase.cnr.ilike(like), SavedCase.court_name.ilike(like)))

    saved = list((await db.scalars(stmt.limit(100))).all()) if payload.include_saved else []
    candidates: list[CaseLookupCandidate] = []
    for row in saved:
        record = await record_from_saved(db, row)
        score = rank_case_record(record, parsed, state=state, district=district, court=court)
        exact = score >= 95 or bool(parsed.cnr and row.cnr == parsed.cnr)
        candidate = CaseLookupCandidate(
            lookup_run_id=run.id,
            saved_case_id=row.id,
            source_kind=CaseSourceKind.SAVED,
            case_record_json=json.loads(_canonical(record)),
            rank_score=score,
            exact_match=exact,
            requires_user_verification=False,
        )
        db.add(candidate)
        candidates.append(candidate)

    candidates.sort(key=lambda item: item.rank_score, reverse=True)
    run.result_count = len(candidates)
    if len(candidates) == 1:
        run.status = CaseLookupStatus.MATCHED
        run.message = "Saved case found immediately. Refresh from the official source when current status is required."
    elif len(candidates) > 1:
        run.status = CaseLookupStatus.AMBIGUOUS
        run.message = "Multiple matching saved cases found. Select the correct court/case before refreshing."
    else:
        run.status = CaseLookupStatus.USER_VERIFICATION_REQUIRED
        capabilities = [DISTRICT_COURT_SOURCE.capability, HIGH_COURT_SOURCE.capability, SUPREME_COURT_SOURCE.capability]
        run.message = "No saved match. Official court lookup requires an approved live connector or supported user-assisted official lookup; CAPTCHA/protected flows are not bypassed."
        run.source_kinds_json = [cap.kind.value for cap in capabilities]
    await db.commit()
    return run, candidates


async def _replace_children(db: AsyncSession, saved_case_id: UUID, record: CaseRecordData) -> None:
    for model in (SavedCaseParty, SavedCaseAdvocate, SavedCaseAct, SavedCaseHearing, SavedCaseOrder, SavedCaseJudgment):
        await db.execute(delete(model).where(model.saved_case_id == saved_case_id))
    for p in record.parties:
        db.add(SavedCaseParty(saved_case_id=saved_case_id, side=p.side, name=p.name, sequence=p.sequence, metadata_json=p.metadata_json))
    for a in record.advocates:
        db.add(SavedCaseAdvocate(saved_case_id=saved_case_id, side=a.side, name=a.name, enrollment_or_reference=a.enrollment_or_reference))
    for a in record.acts:
        db.add(SavedCaseAct(saved_case_id=saved_case_id, act_name=a.act_name, sections_json=a.sections, source_text=a.source_text))
    for h in record.hearing_history:
        db.add(SavedCaseHearing(saved_case_id=saved_case_id, hearing_date=h.hearing_date, purpose_or_stage=h.purpose_or_stage, judge_or_bench=h.judge_or_bench, result_or_note=h.result_or_note, source_reference=h.source_reference, metadata_json=h.metadata_json))
    for o in record.orders:
        db.add(SavedCaseOrder(saved_case_id=saved_case_id, order_date=o.order_date, title=o.title, order_type=o.order_type, document_url=o.document_url, source_url=o.source_url, checksum_sha256=o.checksum_sha256, metadata_json=o.metadata_json))
    for j in record.judgments:
        db.add(SavedCaseJudgment(saved_case_id=saved_case_id, decision_date=j.decision_date, title=j.title, citation=j.citation, document_url=j.document_url, source_url=j.source_url, checksum_sha256=j.checksum_sha256, metadata_json=j.metadata_json))


async def import_case_record(db: AsyncSession, actor: ActorContext, record: CaseRecordData) -> SavedCase:
    if record.source_kind == CaseSourceKind.SAVED:
        raise HTTPException(status_code=400, detail="Imported official records cannot declare source_kind=saved")
    key = source_case_key(record)
    row = None
    if record.cnr:
        row = await db.scalar(select(SavedCase).where(SavedCase.organization_id == actor.organization_id, SavedCase.cnr == record.cnr.upper()))
    if row is None:
        row = await db.scalar(select(SavedCase).where(SavedCase.organization_id == actor.organization_id, SavedCase.source_case_key == key))

    previous_payload = await record_from_saved(db, row) if row else None
    now = datetime.now(UTC)
    if row is None:
        row = SavedCase(
            organization_id=actor.organization_id,
            created_by_membership_id=actor.membership_id,
            source_case_key=key,
            case_number=record.case_number,
            court_name=record.court_name,
            source_kind=record.source_kind,
            source_name=record.source_name,
            fetched_at=record.fetched_at,
        )
        db.add(row)
        await db.flush()

    row.cnr = record.cnr.upper() if record.cnr else None
    row.source_case_key = key
    row.case_type = record.case_type
    row.case_number = record.case_number
    row.year = record.year
    row.case_title = record.case_title
    row.court_name = record.court_name
    row.court_code = record.court_code
    row.court_number = record.court_number
    row.court_level = record.court_level
    row.district = record.district
    row.state = record.state
    row.filing_date = record.filing_date
    row.registration_date = record.registration_date
    row.judge = record.judge
    row.bench = record.bench
    row.case_status = record.status
    row.case_stage = record.case_stage
    row.previous_hearing_date = record.previous_hearing_date
    row.next_hearing_date = record.next_hearing_date
    row.source_kind = record.source_kind
    row.source_name = record.source_name
    row.source_url = record.source_url
    row.source_reference = record.source_reference
    row.fetched_at = record.fetched_at
    row.source_updated_at = record.source_updated_at
    pref = await get_preferences(db, actor)
    row.stale_after = record.fetched_at + timedelta(minutes=pref.default_refresh_minutes)

    await _replace_children(db, row.id, record)
    await db.flush()
    current_payload = record.model_dump(mode="json")
    snapshot = CaseSourceSnapshot(
        saved_case_id=row.id,
        source_kind=record.source_kind,
        source_name=record.source_name,
        source_url=record.source_url,
        fetched_at=record.fetched_at,
        source_updated_at=record.source_updated_at,
        payload_json=current_payload,
        content_hash=_hash_payload(current_payload),
    )
    db.add(snapshot)
    await db.flush()

    previous_snapshot = None
    if row.current_snapshot_id:
        previous_snapshot = await db.get(CaseSourceSnapshot, row.current_snapshot_id)
    row.current_snapshot_id = snapshot.id

    if previous_payload:
        previous_serial = json.loads(_canonical(previous_payload))
        current_serial = json.loads(_canonical(current_payload))
        for field in MATERIAL_CHANGE_FIELDS:
            old = previous_serial.get(field)
            new = current_serial.get(field)
            if old == new:
                continue
            change_type = CaseChangeType.CHANGED
            if old in (None, [], ""):
                change_type = CaseChangeType.ADDED
            elif new in (None, [], ""):
                change_type = CaseChangeType.REMOVED
            db.add(CaseSnapshotChange(
                saved_case_id=row.id,
                previous_snapshot_id=previous_snapshot.id if previous_snapshot else None,
                current_snapshot_id=snapshot.id,
                field_name=field,
                change_type=change_type,
                old_value_json=old,
                new_value_json=new,
                summary=f"{field.replace('_', ' ').title()} {change_type.value}",
                detected_at=now,
            ))

    recent = [c for c in pref.recent_courts_json if c != record.court_name]
    pref.recent_courts_json = [record.court_name, *recent][:10]
    await db.commit()
    await db.refresh(row)
    return row


async def list_saved_cases(db: AsyncSession, actor: ActorContext) -> list[SavedCase]:
    return list((await db.scalars(select(SavedCase).where(SavedCase.organization_id == actor.organization_id).order_by(SavedCase.next_hearing_date, SavedCase.updated_at.desc()))).all())


async def get_saved_case(db: AsyncSession, actor: ActorContext, saved_case_id: UUID) -> tuple[SavedCase, dict, list[CaseSnapshotChange]]:
    row = await db.get(SavedCase, saved_case_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Saved case not found")
    if row.matter_id:
        await enforce_current_matter_access(db, row.matter_id, required=MatterAccessLevel.VIEW)
    record = await record_from_saved(db, row)
    changes = list((await db.scalars(select(CaseSnapshotChange).where(CaseSnapshotChange.saved_case_id == row.id).order_by(CaseSnapshotChange.detected_at.desc()).limit(100))).all())
    return row, record, changes


async def save_lookup_candidate(db: AsyncSession, actor: ActorContext, candidate_id: UUID) -> SavedCase:
    candidate = await db.get(CaseLookupCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Lookup candidate not found")
    run = await db.get(CaseLookupRun, candidate.lookup_run_id)
    if not run or run.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Lookup candidate not found")
    if candidate.saved_case_id:
        row = await db.get(SavedCase, candidate.saved_case_id)
        if row:
            return row
    record = CaseRecordData.model_validate(candidate.case_record_json)
    return await import_case_record(db, actor, record)


async def link_or_create_matter(db: AsyncSession, actor: ActorContext, saved_case_id: UUID, matter_id: UUID | None, create_workspace: bool) -> Matter:
    row, record, _ = await get_saved_case(db, actor, saved_case_id)
    if matter_id:
        await enforce_current_matter_access(db, matter_id, required=MatterAccessLevel.WORK)
        matter = await db.get(Matter, matter_id)
        if not matter:
            raise HTTPException(status_code=404, detail="Matter not found")
    elif create_workspace:
        matter = Matter(
            organization_id=actor.organization_id,
            created_by_user_id=actor.user_id,
            title=record.get("case_title") or f"{record.get('case_type') or 'Case'} {record.get('case_number')}",
            court_name=record.get("court_name"),
            case_number=f"{record.get('case_type') or ''} {record.get('case_number')}/{record.get('year') or ''}".strip(),
            cnr_number=record.get("cnr"),
            jurisdiction=record.get("state") or "India",
            primary_language=MatterLanguage.BILINGUAL,
        )
        db.add(matter)
        await db.flush()
    else:
        raise HTTPException(status_code=400, detail="Provide matter_id or set create_workspace=true")
    row.matter_id = matter.id
    await db.commit()
    await db.refresh(matter)
    return matter
