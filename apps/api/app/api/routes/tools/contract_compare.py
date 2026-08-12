from fastapi import APIRouter, HTTPException

from app.tools.contract_compare.models import ContractCompareRequest, ContractCompareResponse
from app.tools.contract_compare.service import compare_contracts

router = APIRouter()


@router.post("/compare", response_model=ContractCompareResponse)
def compare(payload: ContractCompareRequest) -> ContractCompareResponse:
    try:
        return compare_contracts(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
