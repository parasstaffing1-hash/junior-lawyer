from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.contract import (
    ClauseLibraryRead,
    ClauseUpdate,
    ContractComparison,
    ContractCreate,
    ContractListItem,
    ContractRead,
    ContractUpdate,
    ContractVersionRead,
    DraftResult,
    RiskUpdate,
)
from app.services.contracts import service
from app.services.contracts.catalog import CONTRACT_DEFINITIONS, get_contract_catalog

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("/catalog")
async def contract_catalog() -> list[dict]:
    return get_contract_catalog()


@router.get("/questionnaire/{contract_type}")
async def contract_questionnaire(contract_type: str) -> dict:
    definition = CONTRACT_DEFINITIONS.get(contract_type)
    if definition is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Unknown contract type")
    return {
        "contract_type": contract_type,
        "name_en": definition["name_en"],
        "name_hi": definition["name_hi"],
        "description": definition["description"],
        "questions": definition["questions"],
        "default_clauses": definition["clauses"],
    }


@router.get("/clause-library", response_model=list[ClauseLibraryRead])
async def clause_library(db: AsyncSession = Depends(get_db)) -> list[ClauseLibraryRead]:
    rows = await service.list_clause_library(db)
    return [ClauseLibraryRead.model_validate(item) for item in rows]


@router.post("/clause-library/seed")
async def seed_clause_library(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    return {"created": await service.seed_clause_library(db)}


@router.get("", response_model=list[ContractListItem])
async def list_contracts(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ContractListItem]:
    return await service.list_contracts(db, limit=limit, offset=offset)


@router.post("", response_model=ContractRead, status_code=status.HTTP_201_CREATED)
async def create_contract(
    payload: ContractCreate,
    db: AsyncSession = Depends(get_db),
) -> ContractRead:
    contract = await service.create_contract(db, payload)
    return ContractRead.model_validate(contract)


@router.get("/compare", response_model=ContractComparison)
async def compare_contracts(
    left_id: UUID,
    right_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ContractComparison:
    return await service.compare_contracts(db, left_id=left_id, right_id=right_id)


@router.get("/{contract_id}", response_model=ContractRead)
async def get_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ContractRead:
    return ContractRead.model_validate(await service.get_contract(db, contract_id))


@router.patch("/{contract_id}", response_model=ContractRead)
async def update_contract(
    contract_id: UUID,
    payload: ContractUpdate,
    db: AsyncSession = Depends(get_db),
) -> ContractRead:
    return ContractRead.model_validate(await service.update_contract(db, contract_id, payload))


@router.post("/{contract_id}/draft", response_model=DraftResult)
async def draft_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DraftResult:
    contract, version = await service.draft_contract(db, contract_id)
    return DraftResult(
        contract=ContractRead.model_validate(contract),
        version=ContractVersionRead.model_validate(version),
    )


@router.post("/{contract_id}/review", response_model=ContractRead)
async def review_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ContractRead:
    return ContractRead.model_validate(await service.review_contract(db, contract_id))


@router.post("/{contract_id}/approve", response_model=DraftResult)
async def approve_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DraftResult:
    contract, version = await service.approve_contract(db, contract_id)
    return DraftResult(
        contract=ContractRead.model_validate(contract),
        version=ContractVersionRead.model_validate(version),
    )


@router.get("/{contract_id}/versions", response_model=list[ContractVersionRead])
async def list_versions(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ContractVersionRead]:
    rows = await service.list_versions(db, contract_id)
    return [ContractVersionRead.model_validate(item) for item in rows]


@router.patch("/{contract_id}/clauses/{clause_id}", response_model=ContractRead)
async def update_clause(
    contract_id: UUID,
    clause_id: UUID,
    payload: ClauseUpdate,
    db: AsyncSession = Depends(get_db),
) -> ContractRead:
    return ContractRead.model_validate(
        await service.update_clause(db, contract_id, clause_id, payload)
    )


@router.patch("/{contract_id}/risks/{risk_id}", response_model=ContractRead)
async def update_risk(
    contract_id: UUID,
    risk_id: UUID,
    payload: RiskUpdate,
    db: AsyncSession = Depends(get_db),
) -> ContractRead:
    return ContractRead.model_validate(
        await service.update_risk_status(db, contract_id, risk_id, payload.status)
    )


@router.get("/{contract_id}/download")
async def download_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    contract, path = await service.get_download_path(db, contract_id)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=contract.generated_filename or "contract.docx",
    )
