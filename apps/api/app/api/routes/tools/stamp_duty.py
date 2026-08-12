from fastapi import APIRouter, HTTPException

from app.tools.stamp_duty.models import (
    StampDutyCalculationRequest,
    StampDutyCalculationResponse,
    StampDutyRulePackSummary,
)
from app.tools.stamp_duty.service import (
    StampDutyInputError,
    StampDutyRulePackDateError,
    StampDutyRulePackNotFoundError,
    calculate_stamp_duty,
    list_rule_packs,
)

router = APIRouter()


@router.get("/rule-packs", response_model=list[StampDutyRulePackSummary])
def get_rule_packs() -> list[StampDutyRulePackSummary]:
    return list_rule_packs()


@router.post("/calculate", response_model=StampDutyCalculationResponse)
def calculate(payload: StampDutyCalculationRequest) -> StampDutyCalculationResponse:
    try:
        return calculate_stamp_duty(payload)
    except StampDutyRulePackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (StampDutyRulePackDateError, StampDutyInputError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
