from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.procedure import (
    AgendaItem,
    AttachProcedureRequest,
    ComplianceRead,
    ComplianceUpdate,
    DeadlineCalculationRead,
    DeadlineCalculationRequest,
    DeadlineRead,
    DeadlineUpdate,
    DirectionCreate,
    DirectionExtractionRequest,
    DirectionRead,
    DirectionUpdate,
    HearingBrief,
    HearingCreate,
    HearingRead,
    HearingUpdate,
    MatterDeadlineCreate,
    MatterProcedureRead,
    ProcedurePackCreate,
    ProcedurePackRead,
    ProcedureStats,
    RuleDeadlineCreate,
)
from app.services.procedure import service
from app.services.procedure.calculator import calculate_deadline
from app.services.procedure.catalog import get_catalog

router = APIRouter(prefix="/procedure", tags=["procedure-and-hearings"])


def _procedure_read(row) -> MatterProcedureRead:
    return MatterProcedureRead(
        id=row.id, matter_id=row.matter_id, pack_id=row.pack_id,
        pack_name=row.pack.name_en, pack_version=row.pack.version, status=row.status,
        started_on=row.started_on, completed_on=row.completed_on, notes=row.notes,
        compliances=[ComplianceRead.model_validate(item) for item in row.compliances],
        created_at=row.created_at, updated_at=row.updated_at,
    )


@router.get("/catalog")
async def catalog() -> list[dict]:
    return get_catalog()


@router.post("/packs/seed")
async def seed_packs(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    return {"created": await service.seed_builtin_packs(db)}


@router.get("/packs", response_model=list[ProcedurePackRead])
async def list_packs(db: AsyncSession = Depends(get_db)) -> list[ProcedurePackRead]:
    return [ProcedurePackRead.model_validate(item) for item in await service.list_packs(db)]


@router.post("/packs", response_model=ProcedurePackRead, status_code=status.HTTP_201_CREATED)
async def create_pack(payload: ProcedurePackCreate, db: AsyncSession = Depends(get_db)) -> ProcedurePackRead:
    return ProcedurePackRead.model_validate(await service.create_pack(db, payload))


@router.post("/calculate", response_model=DeadlineCalculationRead)
async def calculate(payload: DeadlineCalculationRequest) -> DeadlineCalculationRead:
    result = calculate_deadline(
        payload.trigger_date, offset_days=payload.offset_days, day_basis=payload.day_basis,
        count_from_next_day=payload.count_from_next_day, adjustment=payload.adjustment,
        holidays=set(payload.holidays),
    )
    return DeadlineCalculationRead(**result.as_dict())


@router.get("/stats", response_model=ProcedureStats)
async def stats(db: AsyncSession = Depends(get_db)) -> ProcedureStats:
    raw = await service.procedure_stats(db)
    return ProcedureStats(**{key: raw[key] for key in ProcedureStats.model_fields})


@router.get("/agenda", response_model=list[AgendaItem])
async def agenda(
    matter_id: UUID | None = None,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> list[AgendaItem]:
    return [AgendaItem.model_validate(item) for item in await service.agenda(db, matter_id=matter_id, days=days)]


@router.post("/matters/{matter_id}/attach", response_model=MatterProcedureRead, status_code=status.HTTP_201_CREATED)
async def attach(matter_id: UUID, payload: AttachProcedureRequest, db: AsyncSession = Depends(get_db)) -> MatterProcedureRead:
    return _procedure_read(await service.attach_procedure(db, matter_id, payload))


@router.get("/matters/{matter_id}", response_model=list[MatterProcedureRead])
async def matter_procedures(matter_id: UUID, db: AsyncSession = Depends(get_db)) -> list[MatterProcedureRead]:
    return [_procedure_read(row) for row in await service.list_matter_procedures(db, matter_id)]


@router.patch("/compliances/{compliance_id}", response_model=ComplianceRead)
async def update_compliance(compliance_id: UUID, payload: ComplianceUpdate, db: AsyncSession = Depends(get_db)) -> ComplianceRead:
    return ComplianceRead.model_validate(await service.update_compliance(db, compliance_id, payload))


@router.get("/deadlines", response_model=list[DeadlineRead])
async def deadlines(matter_id: UUID | None = None, db: AsyncSession = Depends(get_db)) -> list[DeadlineRead]:
    return [DeadlineRead.model_validate(row) for row in await service.list_deadlines(db, matter_id)]


@router.post("/matters/{matter_id}/deadlines/manual", response_model=DeadlineRead, status_code=status.HTTP_201_CREATED)
async def manual_deadline(matter_id: UUID, payload: MatterDeadlineCreate, db: AsyncSession = Depends(get_db)) -> DeadlineRead:
    return DeadlineRead.model_validate(await service.create_manual_deadline(db, matter_id, payload))


@router.post("/matters/{matter_id}/deadlines/from-rule", response_model=DeadlineRead, status_code=status.HTTP_201_CREATED)
async def rule_deadline(matter_id: UUID, payload: RuleDeadlineCreate, db: AsyncSession = Depends(get_db)) -> DeadlineRead:
    return DeadlineRead.model_validate(await service.create_rule_deadline(db, matter_id, payload))


@router.patch("/deadlines/{deadline_id}", response_model=DeadlineRead)
async def patch_deadline(deadline_id: UUID, payload: DeadlineUpdate, db: AsyncSession = Depends(get_db)) -> DeadlineRead:
    return DeadlineRead.model_validate(await service.update_deadline(db, deadline_id, payload))


@router.get("/hearings", response_model=list[HearingRead])
async def hearings(matter_id: UUID | None = None, db: AsyncSession = Depends(get_db)) -> list[HearingRead]:
    return [HearingRead.model_validate(row) for row in await service.list_hearings(db, matter_id)]


@router.post("/hearings", response_model=HearingRead, status_code=status.HTTP_201_CREATED)
async def create_hearing(payload: HearingCreate, db: AsyncSession = Depends(get_db)) -> HearingRead:
    return HearingRead.model_validate(await service.create_hearing(db, payload))


@router.patch("/hearings/{hearing_id}", response_model=HearingRead)
async def patch_hearing(hearing_id: UUID, payload: HearingUpdate, db: AsyncSession = Depends(get_db)) -> HearingRead:
    return HearingRead.model_validate(await service.update_hearing(db, hearing_id, payload))


@router.post("/hearings/{hearing_id}/directions", response_model=DirectionRead, status_code=status.HTTP_201_CREATED)
async def create_direction(hearing_id: UUID, payload: DirectionCreate, db: AsyncSession = Depends(get_db)) -> DirectionRead:
    return DirectionRead.model_validate(await service.create_direction(db, hearing_id, payload))


@router.patch("/directions/{direction_id}", response_model=DirectionRead)
async def patch_direction(direction_id: UUID, payload: DirectionUpdate, db: AsyncSession = Depends(get_db)) -> DirectionRead:
    return DirectionRead.model_validate(await service.update_direction(db, direction_id, payload))


@router.post("/hearings/{hearing_id}/extract-directions", response_model=list[DirectionRead])
async def extract_directions(hearing_id: UUID, payload: DirectionExtractionRequest, db: AsyncSession = Depends(get_db)) -> list[DirectionRead]:
    rows = await service.extract_directions_from_document(db, hearing_id, payload.document_id, payload.order_date)
    return [DirectionRead.model_validate(row) for row in rows]


@router.get("/hearings/{hearing_id}/brief", response_model=HearingBrief)
async def hearing_brief(hearing_id: UUID, db: AsyncSession = Depends(get_db)) -> HearingBrief:
    raw = await service.hearing_brief(db, hearing_id)
    return HearingBrief(
        matter_id=raw["matter_id"],
        matter_title=raw["matter_title"],
        hearing=HearingRead.model_validate(raw["hearing"]),
        previous_hearing=HearingRead.model_validate(raw["previous_hearing"]) if raw["previous_hearing"] else None,
        open_directions=[DirectionRead.model_validate(item) for item in raw["open_directions"]],
        upcoming_deadlines=[DeadlineRead.model_validate(item) for item in raw["upcoming_deadlines"]],
        pending_compliances=raw["pending_compliances"],
        key_facts=raw["key_facts"],
        open_contradictions=raw["open_contradictions"],
        disclaimer=raw["disclaimer"],
    )
