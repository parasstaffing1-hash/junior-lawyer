from fastapi import APIRouter, HTTPException

from app.tools.contract_clause_extractor.models import (
    ClauseExtractRequest,
    ClauseExtractResponse,
    ClauseTypesResponse,
)
from app.tools.contract_clause_extractor.service import (
    ContractClauseExtractorError,
    extract_contract_clauses,
    list_supported_clause_types,
)

router = APIRouter()


@router.get("/types", response_model=ClauseTypesResponse)
def get_supported_clause_types() -> ClauseTypesResponse:
    return list_supported_clause_types()


@router.post("/extract", response_model=ClauseExtractResponse)
def extract_clauses(payload: ClauseExtractRequest) -> ClauseExtractResponse:
    try:
        return extract_contract_clauses(payload)
    except ContractClauseExtractorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
