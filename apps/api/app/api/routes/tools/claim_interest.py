from fastapi import APIRouter, HTTPException, status

from app.tools.claim_interest.models import (
    ClaimInterestCalculationRequest,
    ClaimInterestCalculationResponse,
)
from app.tools.claim_interest.service import ClaimInterestInputError, calculate_claim_interest

router = APIRouter()


@router.post(
    "/calculate",
    response_model=ClaimInterestCalculationResponse,
    status_code=status.HTTP_200_OK,
)
def calculate(request: ClaimInterestCalculationRequest) -> ClaimInterestCalculationResponse:
    try:
        return calculate_claim_interest(request)
    except ClaimInterestInputError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
