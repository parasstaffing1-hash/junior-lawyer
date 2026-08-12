from fastapi import APIRouter

from app.tools.limitation_period.models import (
    LimitationPeriodRequest,
    LimitationPeriodResponse,
)
from app.tools.limitation_period.service import calculate_limitation_period

router = APIRouter()


@router.post("/calculate", response_model=LimitationPeriodResponse)
def calculate_limitation(
    payload: LimitationPeriodRequest,
) -> LimitationPeriodResponse:
    return calculate_limitation_period(payload)
