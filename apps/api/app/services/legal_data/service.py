from __future__ import annotations

import json
import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.integrations import IntegrationConnection, IntegrationProvider
from app.models.legal_corpus import Judgment, JudgmentCitation, JudgmentParagraph, LegalSource, Statute, StatuteSection
from app.models.legal_data_ops import (
    AmendmentEventKind,
    AmendmentReviewStatus,
    IntegrityCheckKind,
    IntegrityStatus,
    JurisdictionPack,
    JurisdictionPackRelease,
    JurisdictionPackSource,
    JurisdictionPackStatus,
    JurisdictionReleaseStatus,
    LegalCorpusCheckpoint,
    LegalDataAlert,
    LegalDataAlertKind,
    LegalDataAlertSeverity,
    LegalDataAlertStatus,
    LegalDataChangeKind,
    LegalDataContentKind,
    LegalDataFeed,
    LegalDataFeedMode,
    LegalDataIngestionItem,
    LegalDataIngestionRun,
    LegalDataIntegrityCheck,
    LegalDataItemStatus,
    LegalDataRunStatus,
    LegalDataRunTrigger,
    LegalDataSourceSnapshot,
    StatuteAmendmentEvent,
)
from app.models.security import AuditOutcome, OrganizationRole
from app.schemas.legal_data import (
    AlertStatusRequest,
    AmendmentReviewRequest,
    JurisdictionPackCreate,
    JurisdictionReleaseCreate,
    LegalDataFeedCreate,
    LegalDataFeedUpdate,
    LegalDataManifest,
)
from app.schemas.research import JudgmentImportRequest, StatuteImportRequest
from app.services.legal_data import engine
from app.services.research import importer as research_importer
from app.services.security.audit import append_audit_event
from app.services.security.context import ActorContext

MANAGER_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.PARTNER}


def _value(value) -> str:
    return getattr(value, "value", str(value))


def _require_manager(actor: ActorContext) -> None:
    if actor.role not in MANAGER_ROLES:
        raise HTTPException(403, "Partner, admin or owner role required for legal-data operations")


async def _audit(db: AsyncSession, actor: ActorContext, action: str, resource_type: str, resource_id: UUID | str | None, metadata: dict | None = None) -> None:
    await append_audit_event(
        db,
        organization_id=actor.organization_id,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        outcome=AuditOutcome.SUCCESS,
        metadata=metadata or {},
    )


def _research_text_hash(text_en: str | None, text_hi: str | None) -> str:
    return hashlib.sha256(f"{text_en or ''}\n{text_hi or ''}".encode("utf-8")).hexdigest()


def _default_domains(source: LegalSource) -> list[str]:
    host = (urlparse(source.base_url or "").hostname or "").casefold()
    return [host] if host else []


async def get_feed(db: AsyncSession, actor: ActorContext, feed_id: UUID) -> LegalDataFeed:
    row = await db.get(LegalDataFeed, feed_id)
    if not row or row.organization_id != actor.organization_id:
        raise HTTPException(404, "Legal-data feed not found")
    return row


async def create_feed(db: AsyncSession, actor: ActorContext, payload: LegalDataFeedCreate) -> LegalDataFeed:
    _require_manager(actor)
    source = await db.get(LegalSource, payload.source_id)
    if not source:
        raise HTTPException(404, "Legal source not found")
    if payload.connection_id:
        connection = await db.get(IntegrationConnection, payload.connection_id)
        if not connection or connection.organization_id != actor.organization_id:
            raise HTTPException(404, "Integration connection not found")
        if _value(connection.provider) != IntegrationProvider.OFFICIAL_LEGAL_IMPORT.value:
            raise HTTPException(422, "Legal-data feeds may only bind to the official legal-import connector")
    if payload.mode == LegalDataFeedMode.FILESYSTEM_DROP and not payload.import_path:
        raise HTTPException(422, "import_path is required for filesystem-drop feeds")
    allowed = payload.allowed_domains or _default_domains(source)
    if not allowed:
        raise HTTPException(422, "At least one authoritative source domain is required")
    row = LegalDataFeed(
        organization_id=actor.organization_id,
        source_id=source.id,
        connection_id=payload.connection_id,
        code=payload.code,
        name=payload.name,
        jurisdiction=payload.jurisdiction,
        state=payload.state,
        content_kind=payload.content_kind,
        mode=payload.mode,
        enabled=True,
        allowed_domains_json=[str(v).casefold().strip() for v in allowed if str(v).strip()],
        schedule_interval_minutes=payload.schedule_interval_minutes,
        stale_after_hours=payload.stale_after_hours,
        import_path=payload.import_path,
        cursor_json={},
        next_due_at=engine.utcnow(),
        metadata_json=payload.metadata,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "A legal-data feed with this code already exists") from exc
    await _audit(db, actor, "legal_data.feed.create", "legal_data_feed", row.id, {"source_id": str(source.id), "mode": _value(payload.mode)})
    await db.commit()
    await db.refresh(row)
    return row


async def list_feeds(db: AsyncSession, actor: ActorContext) -> list[LegalDataFeed]:
    _require_manager(actor)
    return list((await db.scalars(select(LegalDataFeed).where(LegalDataFeed.organization_id == actor.organization_id).order_by(LegalDataFeed.name))).all())


async def update_feed(db: AsyncSession, actor: ActorContext, feed_id: UUID, payload: LegalDataFeedUpdate) -> LegalDataFeed:
    _require_manager(actor)
    row = await get_feed(db, actor, feed_id)
    data = payload.model_dump(exclude_unset=True)
    mapping = {"allowed_domains": "allowed_domains_json", "metadata": "metadata_json"}
    for key, value in data.items():
        setattr(row, mapping.get(key, key), value)
    if row.mode == LegalDataFeedMode.FILESYSTEM_DROP and not row.import_path:
        raise HTTPException(422, "import_path is required for filesystem-drop feeds")
    if not row.allowed_domains_json:
        raise HTTPException(422, "At least one authoritative source domain is required")
    row.next_due_at = engine.next_due(row.last_checked_at, row.schedule_interval_minutes)
    await _audit(db, actor, "legal_data.feed.update", "legal_data_feed", row.id, {"fields": sorted(data)})
    await db.commit(); await db.refresh(row); return row


async def _integrity_check(
    db: AsyncSession,
    *,
    organization_id: UUID,
    feed_id: UUID | None,
    run_id: UUID | None,
    item_id: UUID | None,
    kind: IntegrityCheckKind,
    status: IntegrityStatus,
    source_url: str | None = None,
    expected: str | None = None,
    actual: str | None = None,
    details: dict | None = None,
) -> LegalDataIntegrityCheck:
    row = LegalDataIntegrityCheck(
        organization_id=organization_id,
        feed_id=feed_id,
        run_id=run_id,
        ingestion_item_id=item_id,
        check_kind=kind,
        status=status,
        source_url=source_url,
        expected_value=expected,
        actual_value=actual,
        checked_at=engine.utcnow(),
        details_json=details or {},
    )
    db.add(row)
    return row


async def _upsert_alert(
    db: AsyncSession,
    *,
    organization_id: UUID,
    dedupe_key: str,
    kind: LegalDataAlertKind,
    severity: LegalDataAlertSeverity,
    title: str,
    message: str,
    feed_id: UUID | None = None,
    run_id: UUID | None = None,
    metadata: dict | None = None,
) -> LegalDataAlert:
    now = engine.utcnow()
    row = await db.scalar(select(LegalDataAlert).where(LegalDataAlert.organization_id == organization_id, LegalDataAlert.dedupe_key == dedupe_key).order_by(LegalDataAlert.created_at.desc()).limit(1))
    if row and row.status != LegalDataAlertStatus.RESOLVED:
        row.last_seen_at = now
        row.message = message
        row.severity = severity
        row.feed_id = feed_id
        row.run_id = run_id
        row.metadata_json = metadata or row.metadata_json
        return row
    row = LegalDataAlert(
        organization_id=organization_id,
        feed_id=feed_id,
        run_id=run_id,
        kind=kind,
        severity=severity,
        status=LegalDataAlertStatus.OPEN,
        dedupe_key=dedupe_key,
        title=title,
        message=message,
        first_seen_at=now,
        last_seen_at=now,
        metadata_json=metadata or {},
    )
    db.add(row)
    return row


async def _resolve_alert(db: AsyncSession, organization_id: UUID, dedupe_key: str) -> None:
    row = await db.scalar(select(LegalDataAlert).where(LegalDataAlert.organization_id == organization_id, LegalDataAlert.dedupe_key == dedupe_key, LegalDataAlert.status != LegalDataAlertStatus.RESOLVED).order_by(LegalDataAlert.created_at.desc()).limit(1))
    if row:
        row.status = LegalDataAlertStatus.RESOLVED
        row.resolved_at = engine.utcnow()


async def _capture_before_statute(db: AsyncSession, source_id: UUID, external_id: str) -> tuple[Statute | None, dict[str, dict]]:
    statute = await db.scalar(select(Statute).where(Statute.source_id == source_id, Statute.external_id == external_id))
    if not statute:
        return None, {}
    sections = list((await db.scalars(select(StatuteSection).where(StatuteSection.statute_id == statute.id))).all())
    active: dict[str, StatuteSection] = {}
    for section in sections:
        current = active.get(section.section_number)
        if section.effective_to is not None:
            continue
        if current is None:
            active[section.section_number] = section
            continue
        cur_date = current.effective_from or date.min
        new_date = section.effective_from or date.min
        if new_date >= cur_date:
            active[section.section_number] = section
    return statute, {number: engine.section_snapshot(section) | {"id": str(section.id)} for number, section in active.items()}


async def _prepare_effective_section_rollover(db: AsyncSession, statute: Statute | None, payload: StatuteImportRequest, before_sections: dict[str, dict]) -> None:
    if statute is None:
        return
    for section_payload in payload.sections:
        if not section_payload.effective_from:
            continue
        prior = before_sections.get(section_payload.section_number)
        if not prior or not prior.get("id") or prior.get("effective_to"):
            continue
        new_hash = _research_text_hash(section_payload.text_en, section_payload.text_hi)
        if prior.get("source_hash") == new_hash:
            continue
        row = await db.get(StatuteSection, UUID(prior["id"]))
        if row and row.effective_to is None and row.effective_from != section_payload.effective_from:
            row.effective_to = section_payload.effective_from - timedelta(days=1)
            row.metadata_json = {**(row.metadata_json or {}), "superseded_by_source_effective_date": section_payload.effective_from.isoformat()}
    await db.flush()


async def _record_statute_amendments(
    db: AsyncSession,
    actor: ActorContext,
    item: LegalDataIngestionItem,
    statute: Statute,
    payload: StatuteImportRequest,
    before_statute_hash: str | None,
    before_sections: dict[str, dict],
) -> int:
    events = 0
    after_sections = list((await db.scalars(select(StatuteSection).where(StatuteSection.statute_id == statute.id))).all())
    by_key = {(row.section_number, row.effective_from, row.version_label): row for row in after_sections}
    incoming_numbers: set[str] = set()
    for section_payload in payload.sections:
        incoming_numbers.add(section_payload.section_number)
        before = before_sections.get(section_payload.section_number)
        new_hash = _research_text_hash(section_payload.text_en, section_payload.text_hi)
        prior_hash = before.get("source_hash") if before else None
        if before and prior_hash == new_hash:
            continue
        event_kind = AmendmentEventKind.SECTION_ADDED if not before else AmendmentEventKind.SECTION_CHANGED
        after_row = by_key.get((section_payload.section_number, section_payload.effective_from, section_payload.version_label))
        if after_row is None:
            after_row = next((r for r in after_sections if r.section_number == section_payload.section_number and r.source_hash == new_hash), None)
        event = StatuteAmendmentEvent(
            organization_id=actor.organization_id,
            statute_id=statute.id,
            section_id=after_row.id if after_row else None,
            ingestion_item_id=item.id,
            event_kind=event_kind,
            section_number=section_payload.section_number,
            previous_sha256=prior_hash,
            new_sha256=new_hash,
            effective_date=section_payload.effective_from,
            before_json=before or {},
            after_json=engine.section_payload_snapshot(section_payload),
            review_status=AmendmentReviewStatus.PENDING,
            detected_at=engine.utcnow(),
        )
        db.add(event); events += 1
    if payload.metadata.get("complete_sections") is True:
        for number, before in before_sections.items():
            if number in incoming_numbers:
                continue
            db.add(StatuteAmendmentEvent(
                organization_id=actor.organization_id,
                statute_id=statute.id,
                section_id=UUID(before["id"]) if before.get("id") else None,
                ingestion_item_id=item.id,
                event_kind=AmendmentEventKind.SECTION_REMOVED_FROM_MANIFEST,
                section_number=number,
                previous_sha256=before.get("source_hash"),
                new_sha256=None,
                effective_date=None,
                before_json=before,
                after_json={},
                review_status=AmendmentReviewStatus.PENDING,
                detected_at=engine.utcnow(),
            )); events += 1
    if before_statute_hash and before_statute_hash != statute.source_hash and not events:
        db.add(StatuteAmendmentEvent(
            organization_id=actor.organization_id,
            statute_id=statute.id,
            section_id=None,
            ingestion_item_id=item.id,
            event_kind=AmendmentEventKind.STATUTE_METADATA_CHANGED,
            section_number=None,
            previous_sha256=before_statute_hash,
            new_sha256=statute.source_hash,
            before_json={},
            after_json={"title_en": statute.title_en, "title_hi": statute.title_hi, "act_number": statute.act_number, "act_year": statute.act_year},
            review_status=AmendmentReviewStatus.PENDING,
            detected_at=engine.utcnow(),
        )); events += 1
    return events


async def ingest_manifest(db: AsyncSession, actor: ActorContext, feed_id: UUID, manifest: LegalDataManifest, *, trigger: LegalDataRunTrigger = LegalDataRunTrigger.MANUAL) -> dict:
    _require_manager(actor)
    feed = await get_feed(db, actor, feed_id)
    source = await db.get(LegalSource, feed.source_id)
    if not source:
        raise HTTPException(409, "Feed source no longer exists")
    manifest_payload = manifest.model_dump(mode="json", exclude={"manifest_sha256"})
    manifest_hash = engine.canonical_sha256(manifest_payload)
    if manifest.manifest_sha256 and manifest.manifest_sha256.casefold() != manifest_hash.casefold():
        await _upsert_alert(db, organization_id=actor.organization_id, feed_id=feed.id, dedupe_key=f"manifest-hash:{feed.id}", kind=LegalDataAlertKind.INTEGRITY_FAILURE, severity=LegalDataAlertSeverity.CRITICAL, title="Legal-data manifest hash mismatch", message="The declared manifest SHA-256 did not match the normalized manifest. Nothing was imported.")
        await _integrity_check(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=None, item_id=None, kind=IntegrityCheckKind.PAYLOAD_HASH, status=IntegrityStatus.FAIL, expected=manifest.manifest_sha256, actual=manifest_hash, details={"scope": "manifest"})
        await db.commit()
        raise HTTPException(422, "Manifest SHA-256 mismatch")
    duplicate_run = await db.scalar(select(LegalDataIngestionRun).where(LegalDataIngestionRun.feed_id == feed.id, LegalDataIngestionRun.manifest_sha256 == manifest_hash, LegalDataIngestionRun.status.in_([LegalDataRunStatus.SUCCEEDED, LegalDataRunStatus.PARTIAL])).order_by(LegalDataIngestionRun.finished_at.desc()).limit(1))
    if duplicate_run:
        feed.last_checked_at = engine.utcnow(); feed.next_due_at = engine.next_due(feed.last_checked_at, feed.schedule_interval_minutes)
        await db.commit()
        return {"run": duplicate_run, "items": list((await db.scalars(select(LegalDataIngestionItem).where(LegalDataIngestionItem.run_id == duplicate_run.id).order_by(LegalDataIngestionItem.position))).all()), "duplicate_manifest": True}
    now = engine.utcnow()
    run = LegalDataIngestionRun(
        organization_id=actor.organization_id,
        feed_id=feed.id,
        initiated_by_membership_id=actor.membership_id,
        trigger=trigger,
        status=LegalDataRunStatus.RUNNING,
        manifest_sha256=manifest_hash,
        source_label=manifest.source_label,
        started_at=now,
        items_total=len(manifest.items),
        metadata_json=manifest.metadata,
    )
    db.add(run); await db.flush()
    amendment_count = 0
    for position, raw in enumerate(manifest.items, start=1):
        payload_dict = dict(raw.payload)
        payload_dict["source_code"] = payload_dict.get("source_code") or source.code
        external_id = str(payload_dict.get("external_id") or "")
        actual_hash = engine.canonical_sha256(raw.payload)
        item = LegalDataIngestionItem(run_id=run.id, position=position, kind=raw.kind, external_id=external_id or f"missing-{position}", source_url=raw.source_url, declared_sha256=raw.source_sha256, actual_sha256=actual_hash, status=LegalDataItemStatus.PENDING, change_kind=LegalDataChangeKind.UNCHANGED, metadata_json={})
        db.add(item); await db.flush()
        allowed, host = engine.allowed_source_host(raw.source_url, feed.allowed_domains_json)
        await _integrity_check(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, item_id=item.id, kind=IntegrityCheckKind.SOURCE_HOST, status=IntegrityStatus.PASS if allowed else IntegrityStatus.FAIL, source_url=raw.source_url, expected=",".join(feed.allowed_domains_json), actual=host)
        if not allowed:
            item.status = LegalDataItemStatus.REJECTED; item.error_message = "Source URL is not HTTPS or is outside the feed allowlist"; run.items_failed += 1
            await _upsert_alert(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, dedupe_key=f"source-host:{feed.id}:{host}", kind=LegalDataAlertKind.INTEGRITY_FAILURE, severity=LegalDataAlertSeverity.CRITICAL, title="Rejected non-authoritative legal-data source", message=f"A manifest item used an unapproved source host: {host or 'unknown'}")
            continue
        if payload_dict.get("source_code") != source.code:
            item.status = LegalDataItemStatus.REJECTED; item.error_message = "Payload source_code does not match feed source"; run.items_failed += 1
            await _integrity_check(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, item_id=item.id, kind=IntegrityCheckKind.SCHEMA, status=IntegrityStatus.FAIL, source_url=raw.source_url, expected=source.code, actual=str(payload_dict.get("source_code")), details={"field": "source_code"})
            continue
        if raw.source_sha256 and raw.source_sha256.casefold() != actual_hash.casefold():
            item.status = LegalDataItemStatus.REJECTED; item.error_message = "Item payload SHA-256 mismatch"; run.items_failed += 1
            await _integrity_check(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, item_id=item.id, kind=IntegrityCheckKind.PAYLOAD_HASH, status=IntegrityStatus.FAIL, source_url=raw.source_url, expected=raw.source_sha256, actual=actual_hash)
            await _upsert_alert(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, dedupe_key=f"payload-hash:{feed.id}:{external_id}", kind=LegalDataAlertKind.INTEGRITY_FAILURE, severity=LegalDataAlertSeverity.CRITICAL, title="Legal-data payload hash mismatch", message=f"Record {external_id or position} was rejected because its declared SHA-256 did not match.")
            continue
        await _integrity_check(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, item_id=item.id, kind=IntegrityCheckKind.PAYLOAD_HASH, status=IntegrityStatus.PASS, source_url=raw.source_url, expected=raw.source_sha256 or actual_hash, actual=actual_hash)
        try:
            if raw.kind == "statute":
                validated = StatuteImportRequest.model_validate(payload_dict)
                if feed.content_kind == LegalDataContentKind.JUDGMENT:
                    raise ValueError("Statute item is not permitted by a judgment-only feed")
                before, before_sections = await _capture_before_statute(db, source.id, validated.external_id)
                before_hash = before.source_hash if before else None
                await _prepare_effective_section_rollover(db, before, validated, before_sections)
                record = await research_importer.import_statute(db, validated)
                item.resource_type = "statute"; item.resource_id = record.id; item.before_sha256 = before_hash; item.after_sha256 = record.source_hash
                item.change_kind = engine.classify_hash_change(before_hash, record.source_hash or actual_hash)
                amendment_count += await _record_statute_amendments(db, actor, item, record, validated, before_hash, before_sections)
            else:
                validated = JudgmentImportRequest.model_validate(payload_dict)
                if feed.content_kind == LegalDataContentKind.STATUTE:
                    raise ValueError("Judgment item is not permitted by a statute-only feed")
                before = await db.scalar(select(Judgment).where(Judgment.source_id == source.id, Judgment.external_id == validated.external_id))
                before_hash = before.source_hash if before else None
                record = await research_importer.import_judgment(db, validated)
                item.resource_type = "judgment"; item.resource_id = record.id; item.before_sha256 = before_hash; item.after_sha256 = record.source_hash
                item.change_kind = engine.classify_hash_change(before_hash, record.source_hash or actual_hash)
            item.status = LegalDataItemStatus.UNCHANGED if item.change_kind == LegalDataChangeKind.UNCHANGED else LegalDataItemStatus.IMPORTED
            if item.status == LegalDataItemStatus.UNCHANGED: run.items_unchanged += 1
            else: run.items_changed += 1
            run.items_succeeded += 1
            previous_snapshot = await db.scalar(select(LegalDataSourceSnapshot).where(LegalDataSourceSnapshot.feed_id == feed.id, LegalDataSourceSnapshot.kind == raw.kind, LegalDataSourceSnapshot.external_id == item.external_id).order_by(LegalDataSourceSnapshot.observed_at.desc()).limit(1))
            db.add(LegalDataSourceSnapshot(organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, kind=raw.kind, external_id=item.external_id, source_url=raw.source_url, content_sha256=actual_hash, previous_sha256=previous_snapshot.content_sha256 if previous_snapshot else None, verification_status=IntegrityStatus.PASS, observed_at=engine.utcnow(), metadata_json={"resource_id": str(item.resource_id)}))
            await _integrity_check(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, item_id=item.id, kind=IntegrityCheckKind.SCHEMA, status=IntegrityStatus.PASS, source_url=raw.source_url, details={"kind": raw.kind})
        except Exception as exc:
            item.status = LegalDataItemStatus.FAILED; item.error_message = f"{type(exc).__name__}: {exc}"[:8000]; run.items_failed += 1
            await _integrity_check(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, item_id=item.id, kind=IntegrityCheckKind.SCHEMA, status=IntegrityStatus.FAIL, source_url=raw.source_url, actual=item.error_message)
    run.finished_at = engine.utcnow()
    if run.items_failed == 0:
        run.status = LegalDataRunStatus.SUCCEEDED
    elif run.items_succeeded > 0:
        run.status = LegalDataRunStatus.PARTIAL
    else:
        run.status = LegalDataRunStatus.FAILED
    feed.last_checked_at = run.finished_at
    feed.next_due_at = engine.next_due(feed.last_checked_at, feed.schedule_interval_minutes)
    feed.last_manifest_sha256 = manifest_hash
    if run.items_succeeded > 0 and run.status in {LegalDataRunStatus.SUCCEEDED, LegalDataRunStatus.PARTIAL}:
        feed.last_success_at = run.finished_at
        await _resolve_alert(db, actor.organization_id, f"source-stale:{feed.id}")
    if run.items_failed:
        await _upsert_alert(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, dedupe_key=f"ingestion-failure:{feed.id}", kind=LegalDataAlertKind.INGESTION_FAILURE, severity=LegalDataAlertSeverity.HIGH if run.items_succeeded else LegalDataAlertSeverity.CRITICAL, title="Legal-data ingestion needs review", message=f"{run.items_failed} of {run.items_total} records failed or were rejected.")
    else:
        await _resolve_alert(db, actor.organization_id, f"ingestion-failure:{feed.id}")
    if amendment_count:
        await _upsert_alert(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=run.id, dedupe_key=f"amendments:{run.id}", kind=LegalDataAlertKind.AMENDMENT_DETECTED, severity=LegalDataAlertSeverity.WARNING, title="Statutory changes detected", message=f"{amendment_count} statute/section changes were detected and require legal-data review.", metadata={"amendment_count": amendment_count})
    checkpoint = await capture_checkpoint(db, actor, run_id=run.id)
    await _audit(db, actor, "legal_data.manifest.ingest", "legal_data_ingestion_run", run.id, {"status": _value(run.status), "items": run.items_total, "amendments": amendment_count, "checkpoint": str(checkpoint.id)})
    await db.commit()
    items = list((await db.scalars(select(LegalDataIngestionItem).where(LegalDataIngestionItem.run_id == run.id).order_by(LegalDataIngestionItem.position))).all())
    return {"run": run, "items": items, "duplicate_manifest": False}


async def capture_checkpoint(db: AsyncSession, actor: ActorContext, *, run_id: UUID | None = None) -> LegalCorpusCheckpoint:
    async def count(model) -> int:
        return int(await db.scalar(select(func.count()).select_from(model)) or 0)
    statutes_count = await count(Statute); sections_count = await count(StatuteSection); judgments_count = await count(Judgment); paragraphs_count = await count(JudgmentParagraph); citations_count = await count(JudgmentCitation)
    statute_hashes = list((await db.execute(select(Statute.id, Statute.source_hash).order_by(Statute.id))).all())
    judgment_hashes = list((await db.execute(select(Judgment.id, Judgment.source_hash).order_by(Judgment.id))).all())
    aggregate = engine.canonical_sha256({"statutes": [(str(i), h) for i, h in statute_hashes], "judgments": [(str(i), h) for i, h in judgment_hashes]})
    row = LegalCorpusCheckpoint(organization_id=actor.organization_id, run_id=run_id, statutes=statutes_count, sections=sections_count, judgments=judgments_count, paragraphs=paragraphs_count, citations=citations_count, aggregate_sha256=aggregate, captured_at=engine.utcnow(), metadata_json={})
    db.add(row); await db.flush(); return row


async def list_runs(db: AsyncSession, actor: ActorContext, *, limit: int = 100) -> list[LegalDataIngestionRun]:
    _require_manager(actor)
    return list((await db.scalars(select(LegalDataIngestionRun).where(LegalDataIngestionRun.organization_id == actor.organization_id).order_by(LegalDataIngestionRun.started_at.desc()).limit(min(500, max(1, limit))))).all())


async def run_detail(db: AsyncSession, actor: ActorContext, run_id: UUID) -> dict:
    _require_manager(actor)
    run = await db.get(LegalDataIngestionRun, run_id)
    if not run or run.organization_id != actor.organization_id: raise HTTPException(404, "Ingestion run not found")
    items = list((await db.scalars(select(LegalDataIngestionItem).where(LegalDataIngestionItem.run_id == run.id).order_by(LegalDataIngestionItem.position))).all())
    return {"run": run, "items": items}


async def list_amendments(db: AsyncSession, actor: ActorContext, *, status: str | None = None, limit: int = 200) -> list[StatuteAmendmentEvent]:
    _require_manager(actor)
    stmt = select(StatuteAmendmentEvent).where(StatuteAmendmentEvent.organization_id == actor.organization_id)
    if status: stmt = stmt.where(StatuteAmendmentEvent.review_status == status)
    return list((await db.scalars(stmt.order_by(StatuteAmendmentEvent.detected_at.desc()).limit(min(1000, max(1, limit))))).all())


async def review_amendment(db: AsyncSession, actor: ActorContext, amendment_id: UUID, payload: AmendmentReviewRequest) -> StatuteAmendmentEvent:
    _require_manager(actor)
    row = await db.get(StatuteAmendmentEvent, amendment_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Amendment event not found")
    row.review_status = payload.status; row.reviewed_at = engine.utcnow(); row.reviewed_by_membership_id = actor.membership_id; row.review_note = payload.note
    if row.ingestion_item_id:
        item = await db.get(LegalDataIngestionItem, row.ingestion_item_id)
        if item:
            pending = int(await db.scalar(select(func.count()).select_from(StatuteAmendmentEvent).where(StatuteAmendmentEvent.ingestion_item_id == item.id, StatuteAmendmentEvent.review_status == AmendmentReviewStatus.PENDING, StatuteAmendmentEvent.id != row.id)) or 0)
            if pending == 0:
                await _resolve_alert(db, actor.organization_id, f"amendments:{item.run_id}")
    await _audit(db, actor, "legal_data.amendment.review", "statute_amendment_event", row.id, {"status": _value(payload.status)})
    await db.commit(); await db.refresh(row); return row


def _safe_import_directory(feed: LegalDataFeed) -> Path:
    root = settings.legal_data_import_root.expanduser().resolve()
    candidate = (root / str(feed.import_path or "")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("Feed import path escapes LEGAL_DATA_IMPORT_ROOT") from exc
    return candidate


async def sync_feed(db: AsyncSession, actor: ActorContext, feed_id: UUID, *, trigger: LegalDataRunTrigger = LegalDataRunTrigger.WORKER) -> dict:
    _require_manager(actor)
    feed = await get_feed(db, actor, feed_id)
    now = engine.utcnow(); feed.last_checked_at = now; feed.next_due_at = engine.next_due(now, feed.schedule_interval_minutes)
    if not feed.enabled:
        await db.commit(); return {"feed_id": str(feed.id), "status": "disabled", "runs": []}
    if feed.mode in {LegalDataFeedMode.MANUAL_MANIFEST, LegalDataFeedMode.INTEGRATION_PUSH}:
        await db.commit(); return {"feed_id": str(feed.id), "status": "push_or_manual_only", "runs": []}
    directory = _safe_import_directory(feed)
    if not directory.exists() or not directory.is_dir():
        await _upsert_alert(db, organization_id=actor.organization_id, feed_id=feed.id, dedupe_key=f"ingestion-failure:{feed.id}", kind=LegalDataAlertKind.INGESTION_FAILURE, severity=LegalDataAlertSeverity.HIGH, title="Legal-data import directory unavailable", message=f"Configured import drop does not exist: {feed.import_path}")
        await db.commit(); return {"feed_id": str(feed.id), "status": "directory_missing", "runs": []}
    files = sorted([p for p in directory.glob("*.json") if p.is_file()])[:100]
    results: list[dict] = []
    for path in files:
        if path.stat().st_size > settings.legal_data_max_manifest_mb * 1024 * 1024:
            results.append({"file": path.name, "status": "rejected_too_large"}); continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            manifest = LegalDataManifest.model_validate(raw)
            detail = await ingest_manifest(db, actor, feed.id, manifest, trigger=trigger)
            results.append({"file": path.name, "status": _value(detail["run"].status), "run_id": str(detail["run"].id), "duplicate": detail.get("duplicate_manifest", False)})
        except Exception as exc:
            results.append({"file": path.name, "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:1000]})
    feed.last_checked_at = engine.utcnow(); feed.next_due_at = engine.next_due(feed.last_checked_at, feed.schedule_interval_minutes)
    await db.commit()
    return {"feed_id": str(feed.id), "status": "processed", "files_seen": len(files), "runs": results}


async def integrity_sweep(db: AsyncSession, actor: ActorContext) -> dict:
    _require_manager(actor)
    feeds = list((await db.scalars(select(LegalDataFeed).where(LegalDataFeed.organization_id == actor.organization_id, LegalDataFeed.enabled.is_(True)))).all())
    stale = 0; healthy = 0
    now = engine.utcnow()
    for feed in feeds:
        source = await db.get(LegalSource, feed.source_id)
        source_ok = bool(source and source.enabled and source.official)
        await _integrity_check(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=None, item_id=None, kind=IntegrityCheckKind.SOURCE_ENABLED, status=IntegrityStatus.PASS if source_ok else IntegrityStatus.FAIL, expected="official+enabled", actual=f"official={getattr(source,'official',None)},enabled={getattr(source,'enabled',None)}")
        if not source_ok:
            await _upsert_alert(db, organization_id=actor.organization_id, feed_id=feed.id, dedupe_key=f"source-health:{feed.id}", kind=LegalDataAlertKind.INTEGRITY_FAILURE, severity=LegalDataAlertSeverity.HIGH, title="Legal-data source is not healthy", message="The feed source is missing, disabled, or not marked official.")
        else:
            await _resolve_alert(db, actor.organization_id, f"source-health:{feed.id}")
        stale_now = engine.is_stale(feed.last_success_at, feed.stale_after_hours, now=now)
        await _integrity_check(db, organization_id=actor.organization_id, feed_id=feed.id, run_id=None, item_id=None, kind=IntegrityCheckKind.FRESHNESS, status=IntegrityStatus.WARNING if stale_now else IntegrityStatus.PASS, expected=f"<={feed.stale_after_hours}h", actual=feed.last_success_at.isoformat() if feed.last_success_at else "never")
        if stale_now:
            stale += 1
            await _upsert_alert(db, organization_id=actor.organization_id, feed_id=feed.id, dedupe_key=f"source-stale:{feed.id}", kind=LegalDataAlertKind.SOURCE_STALE, severity=LegalDataAlertSeverity.WARNING, title="Legal-data feed is stale", message=f"{feed.name} has not completed a successful import within {feed.stale_after_hours} hours.")
        else:
            healthy += 1; await _resolve_alert(db, actor.organization_id, f"source-stale:{feed.id}")
    await _audit(db, actor, "legal_data.integrity.sweep", "organization", actor.organization_id, {"feeds": len(feeds), "stale": stale})
    await db.commit(); return {"feeds": len(feeds), "stale": stale, "healthy": healthy}


async def create_pack(db: AsyncSession, actor: ActorContext, payload: JurisdictionPackCreate) -> JurisdictionPack:
    _require_manager(actor)
    row = JurisdictionPack(organization_id=actor.organization_id, pack_key=payload.pack_key, name=payload.name, jurisdiction=payload.jurisdiction, state=payload.state, languages_json=payload.languages, status=JurisdictionPackStatus.DRAFT, description=payload.description, metadata_json=payload.metadata)
    db.add(row)
    try: await db.flush()
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "Jurisdiction pack key already exists") from exc
    await _audit(db, actor, "legal_data.pack.create", "jurisdiction_pack", row.id)
    await db.commit(); await db.refresh(row); return row


async def list_packs(db: AsyncSession, actor: ActorContext) -> list[JurisdictionPack]:
    _require_manager(actor)
    return list((await db.scalars(select(JurisdictionPack).where(JurisdictionPack.organization_id == actor.organization_id).order_by(JurisdictionPack.name))).all())


async def create_pack_release(db: AsyncSession, actor: ActorContext, pack_id: UUID, payload: JurisdictionReleaseCreate) -> JurisdictionPackRelease:
    _require_manager(actor)
    pack = await db.get(JurisdictionPack, pack_id)
    if not pack or pack.organization_id != actor.organization_id: raise HTTPException(404, "Jurisdiction pack not found")
    source_payloads = [item.model_dump(mode="json") for item in payload.sources]
    manifest_hash = engine.release_manifest_hash(pack_key=pack.pack_key, version=payload.version, effective_from=payload.effective_from, effective_to=payload.effective_to, sources=source_payloads)
    row = JurisdictionPackRelease(pack_id=pack.id, version=payload.version, status=JurisdictionReleaseStatus.DRAFT, effective_from=payload.effective_from, effective_to=payload.effective_to, manifest_sha256=manifest_hash, notes=payload.notes, metadata_json=payload.metadata)
    db.add(row)
    try: await db.flush()
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "This jurisdiction-pack version already exists") from exc
    for item in payload.sources:
        source = await db.get(LegalSource, item.source_id)
        if not source: raise HTTPException(404, f"Legal source {item.source_id} not found")
        if item.feed_id:
            feed = await get_feed(db, actor, item.feed_id)
            if feed.source_id != item.source_id: raise HTTPException(422, "Pack source feed does not match its legal source")
        db.add(JurisdictionPackSource(release_id=row.id, source_id=item.source_id, feed_id=item.feed_id, required=item.required, maximum_age_hours=item.maximum_age_hours, metadata_json=item.metadata))
    await _audit(db, actor, "legal_data.pack_release.create", "jurisdiction_pack_release", row.id, {"version": row.version})
    await db.commit(); await db.refresh(row); return row


async def list_pack_releases(db: AsyncSession, actor: ActorContext, pack_id: UUID) -> list[JurisdictionPackRelease]:
    _require_manager(actor)
    pack = await db.get(JurisdictionPack, pack_id)
    if not pack or pack.organization_id != actor.organization_id: raise HTTPException(404, "Jurisdiction pack not found")
    return list((await db.scalars(select(JurisdictionPackRelease).where(JurisdictionPackRelease.pack_id == pack.id).order_by(JurisdictionPackRelease.created_at.desc()))).all())


async def activate_pack_release(db: AsyncSession, actor: ActorContext, release_id: UUID) -> JurisdictionPackRelease:
    _require_manager(actor)
    release = await db.get(JurisdictionPackRelease, release_id)
    if not release: raise HTTPException(404, "Jurisdiction pack release not found")
    pack = await db.get(JurisdictionPack, release.pack_id)
    if not pack or pack.organization_id != actor.organization_id: raise HTTPException(404, "Jurisdiction pack not found")
    refs = list((await db.scalars(select(JurisdictionPackSource).where(JurisdictionPackSource.release_id == release.id))).all())
    blockers: list[str] = []
    now = engine.utcnow()
    for ref in refs:
        source = await db.get(LegalSource, ref.source_id)
        if ref.required and (not source or not source.official or not source.enabled):
            blockers.append(f"Source {ref.source_id} is not official and enabled")
        if ref.required and not ref.feed_id:
            blockers.append(f"Required source {getattr(source,'name',ref.source_id)} has no freshness-tracked feed")
        if ref.feed_id:
            feed = await db.get(LegalDataFeed, ref.feed_id)
            if not feed or feed.organization_id != actor.organization_id or feed.source_id != ref.source_id:
                blockers.append(f"Feed {ref.feed_id} is invalid for source {ref.source_id}")
            elif engine.is_stale(feed.last_success_at, ref.maximum_age_hours, now=now):
                blockers.append(f"Feed {feed.name} is older than {ref.maximum_age_hours} hours")
        pending = int(await db.scalar(select(func.count()).select_from(StatuteAmendmentEvent).join(Statute, Statute.id == StatuteAmendmentEvent.statute_id).where(Statute.source_id == ref.source_id, StatuteAmendmentEvent.organization_id == actor.organization_id, StatuteAmendmentEvent.review_status == AmendmentReviewStatus.PENDING)) or 0)
        if ref.required and pending:
            blockers.append(f"Source {getattr(source,'name',ref.source_id)} has {pending} unreviewed statutory change(s)")
    if blockers:
        await _upsert_alert(db, organization_id=actor.organization_id, dedupe_key=f"pack-source:{release.id}", kind=LegalDataAlertKind.PACK_SOURCE_UNHEALTHY, severity=LegalDataAlertSeverity.HIGH, title="Jurisdiction pack cannot be activated", message="; ".join(blockers[:10]), metadata={"blockers": blockers})
        await db.commit()
        raise HTTPException(409, {"message": "Jurisdiction pack release is not activation-ready", "blockers": blockers})
    previous = list((await db.scalars(select(JurisdictionPackRelease).where(JurisdictionPackRelease.pack_id == pack.id, JurisdictionPackRelease.status == JurisdictionReleaseStatus.ACTIVE, JurisdictionPackRelease.id != release.id))).all())
    for old in previous: old.status = JurisdictionReleaseStatus.RETIRED
    release.status = JurisdictionReleaseStatus.ACTIVE; release.approved_by_membership_id = actor.membership_id; release.activated_at = now
    pack.status = JurisdictionPackStatus.ACTIVE; pack.active_release_version = release.version
    await _resolve_alert(db, actor.organization_id, f"pack-source:{release.id}")
    await _audit(db, actor, "legal_data.pack_release.activate", "jurisdiction_pack_release", release.id, {"version": release.version})
    await db.commit(); await db.refresh(release); return release


async def list_alerts(db: AsyncSession, actor: ActorContext, *, status: str | None = None, limit: int = 200) -> list[LegalDataAlert]:
    _require_manager(actor)
    stmt = select(LegalDataAlert).where(LegalDataAlert.organization_id == actor.organization_id)
    if status: stmt = stmt.where(LegalDataAlert.status == status)
    return list((await db.scalars(stmt.order_by(LegalDataAlert.last_seen_at.desc()).limit(min(1000, max(1, limit))))).all())


async def update_alert_status(db: AsyncSession, actor: ActorContext, alert_id: UUID, payload: AlertStatusRequest) -> LegalDataAlert:
    _require_manager(actor)
    row = await db.get(LegalDataAlert, alert_id)
    if not row or row.organization_id != actor.organization_id: raise HTTPException(404, "Legal-data alert not found")
    row.status = payload.status
    now = engine.utcnow()
    if payload.status == LegalDataAlertStatus.ACKNOWLEDGED: row.acknowledged_at = now
    if payload.status == LegalDataAlertStatus.RESOLVED: row.resolved_at = now; row.resolved_by_membership_id = actor.membership_id
    await _audit(db, actor, "legal_data.alert.update", "legal_data_alert", row.id, {"status": _value(payload.status)})
    await db.commit(); await db.refresh(row); return row


async def list_integrity_checks(db: AsyncSession, actor: ActorContext, *, limit: int = 300) -> list[LegalDataIntegrityCheck]:
    _require_manager(actor)
    return list((await db.scalars(select(LegalDataIntegrityCheck).where(LegalDataIntegrityCheck.organization_id == actor.organization_id).order_by(LegalDataIntegrityCheck.checked_at.desc()).limit(min(2000, max(1, limit))))).all())


async def list_checkpoints(db: AsyncSession, actor: ActorContext, *, limit: int = 50) -> list[LegalCorpusCheckpoint]:
    _require_manager(actor)
    return list((await db.scalars(select(LegalCorpusCheckpoint).where(LegalCorpusCheckpoint.organization_id == actor.organization_id).order_by(LegalCorpusCheckpoint.captured_at.desc()).limit(min(500, max(1, limit))))).all())


async def dashboard(db: AsyncSession, actor: ActorContext) -> dict:
    _require_manager(actor)
    now = engine.utcnow(); day_ago = now - timedelta(hours=24)
    feeds = list((await db.scalars(select(LegalDataFeed).where(LegalDataFeed.organization_id == actor.organization_id))).all())
    stale = sum(1 for feed in feeds if feed.enabled and engine.is_stale(feed.last_success_at, feed.stale_after_hours, now=now))
    open_alerts = int(await db.scalar(select(func.count()).select_from(LegalDataAlert).where(LegalDataAlert.organization_id == actor.organization_id, LegalDataAlert.status != LegalDataAlertStatus.RESOLVED)) or 0)
    pending_amendments = int(await db.scalar(select(func.count()).select_from(StatuteAmendmentEvent).where(StatuteAmendmentEvent.organization_id == actor.organization_id, StatuteAmendmentEvent.review_status == AmendmentReviewStatus.PENDING)) or 0)
    runs_24h = int(await db.scalar(select(func.count()).select_from(LegalDataIngestionRun).where(LegalDataIngestionRun.organization_id == actor.organization_id, LegalDataIngestionRun.started_at >= day_ago)) or 0)
    failed_runs = int(await db.scalar(select(func.count()).select_from(LegalDataIngestionRun).where(LegalDataIngestionRun.organization_id == actor.organization_id, LegalDataIngestionRun.started_at >= day_ago, LegalDataIngestionRun.status.in_([LegalDataRunStatus.FAILED, LegalDataRunStatus.PARTIAL]))) or 0)
    active_packs = int(await db.scalar(select(func.count()).select_from(JurisdictionPack).where(JurisdictionPack.organization_id == actor.organization_id, JurisdictionPack.status == JurisdictionPackStatus.ACTIVE)) or 0)
    latest_checkpoint = await db.scalar(select(LegalCorpusCheckpoint).where(LegalCorpusCheckpoint.organization_id == actor.organization_id).order_by(LegalCorpusCheckpoint.captured_at.desc()).limit(1))
    recent_runs = list((await db.scalars(select(LegalDataIngestionRun).where(LegalDataIngestionRun.organization_id == actor.organization_id).order_by(LegalDataIngestionRun.started_at.desc()).limit(8))).all())
    alerts = list((await db.scalars(select(LegalDataAlert).where(LegalDataAlert.organization_id == actor.organization_id, LegalDataAlert.status != LegalDataAlertStatus.RESOLVED).order_by(LegalDataAlert.last_seen_at.desc()).limit(8))).all())
    return {"feeds": len(feeds), "stale_feeds": stale, "open_alerts": open_alerts, "pending_amendments": pending_amendments, "runs_24h": runs_24h, "failed_runs_24h": failed_runs, "active_packs": active_packs, "latest_checkpoint": latest_checkpoint, "recent_runs": recent_runs, "alerts": alerts}
