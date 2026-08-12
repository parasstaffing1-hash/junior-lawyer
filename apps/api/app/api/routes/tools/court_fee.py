from fastapi import APIRouter, HTTPException

from app.tools.court_fee.models import (
    CourtFeeCalculationRequest,
    CourtFeeCalculationResponse,
    CourtFeeRulePackSummary,
)
from app.tools.court_fee.service import (
    CourtFeeInputError,
    CourtFeeRulePackDateError,
    CourtFeeRulePackNotFoundError,
    calculate_court_fee,
    list_rule_packs,
)

router = APIRouter()


@router.get("/rule-packs", response_model=list[CourtFeeRulePackSummary])
def get_rule_packs() -> list[CourtFeeRulePackSummary]:
    return list_rule_packs()


@router.post("/calculate", response_model=CourtFeeCalculationResponse)
def calculate(payload: CourtFeeCalculationRequest) -> CourtFeeCalculationResponse:
    try:
        return calculate_court_fee(payload)
    except CourtFeeRulePackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (CourtFeeRulePackDateError, CourtFeeInputError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
