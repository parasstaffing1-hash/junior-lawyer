from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.case_lookup import (
    CaseCandidateRead,
    CaseWorkspaceResult,
    CaseLookupPreferenceRead,
    CaseLookupPreferenceUpdate,
    CaseLookupRequest,
    CaseLookupResponse,
    CaseRecordData,
    LinkCaseMatterRequest,
    OfficialCaseImportRequest,
    SavedCaseChange,
    SavedCaseDetailRead,
    SavedCaseSummaryRead,
)
from app.services.case_lookup import service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router = APIRouter(prefix="/case-lookup", tags=["case-lookup"])


@router.get("/preferences", response_model=CaseLookupPreferenceRead)
async def preferences(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return CaseLookupPreferenceRead.model_validate(await service.get_preferences(db, actor))


@router.patch("/preferences", response_model=CaseLookupPreferenceRead)
async def patch_preferences(payload: CaseLookupPreferenceUpdate, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return CaseLookupPreferenceRead.model_validate(await service.update_preferences(db, actor, payload))


@router.post("/search", response_model=CaseLookupResponse)
async def search(payload: CaseLookupRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    run, candidates = await service.search_cases(db, actor, payload)
    return CaseLookupResponse(
        run_id=run.id,
        status=run.status,
        detected_kind=run.detected_kind,
        parsed=run.parsed_json,
        message=run.message,
        candidates=[CaseCandidateRead(
            id=item.id,
            saved_case_id=item.saved_case_id,
            source_kind=item.source_kind,
            case_record=CaseRecordData.model_validate(item.case_record_json),
            rank_score=item.rank_score,
            exact_match=item.exact_match,
            requires_user_verification=item.requires_user_verification,
        ) for item in candidates],
    )


@router.post("/import-official", response_model=SavedCaseDetailRead, status_code=201)
async def import_official(payload: OfficialCaseImportRequest, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row = await service.import_case_record(db, actor, payload.record)
    row, record, changes = await service.get_saved_case(db, actor, row.id)
    return SavedCaseDetailRead(
        id=row.id,
        matter_id=row.matter_id,
        record=CaseRecordData.model_validate(record),
        changes=[SavedCaseChange(
            id=str(change.id),
            field=change.field_name,
            change_type=change.change_type.value if hasattr(change.change_type, "value") else change.change_type,
            old=change.old_value_json,
            new=change.new_value_json,
            summary=change.summary,
            detected_at=change.detected_at,
        ) for change in changes],
        stale=bool(row.stale_after and row.stale_after < datetime.now(UTC)),
    )


@router.post("/candidates/{candidate_id}/save", response_model=SavedCaseSummaryRead)
async def save_candidate(candidate_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return SavedCaseSummaryRead.model_validate(await service.save_lookup_candidate(db, actor, candidate_id))


@router.get("/saved", response_model=list[SavedCaseSummaryRead])
async def saved(actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    return [SavedCaseSummaryRead.model_validate(row) for row in await service.list_saved_cases(db, actor)]


@router.get("/saved/{saved_case_id}", response_model=SavedCaseDetailRead)
async def saved_detail(saved_case_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db)):
    row, record, changes = await service.get_saved_case(db, actor, saved_case_id)
    return SavedCaseDetailRead(
        id=row.id,
        matter_id=row.matter_id,
        record=CaseRecordData.model_validate(record),
        changes=[SavedCaseChange(
            id=str(change.id),
            field=change.field_name,
            change_type=change.change_type.value if hasattr(change.change_type, "value") else change.change_type,
            old=change.old_value_json,
            new=change.new_value_json,
            summary=change.summary,
            detected_at=change.detected_at,
        ) for change in changes],
        stale=bool(row.stale_after and row.stale_after < datetime.now(UTC)),
    )


@router.post("/saved/{saved_case_id}/workspace", response_model=CaseWorkspaceResult)
async def workspace(saved_case_id: UUID, actor: ActorContext = Depends(require_actor), db: AsyncSession = Depends(get_db), payload: LinkCaseMatterRequest = Body(default_factory=LinkCaseMatterRequest)):
    matter = await service.link_or_create_matter(db, actor, saved_case_id, payload.matter_id, payload.create_workspace)
    return CaseWorkspaceResult(matter_id=str(matter.id), title=matter.title)
