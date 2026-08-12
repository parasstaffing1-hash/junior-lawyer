from fastapi import APIRouter, HTTPException

from app.tools.key_dates_obligations.models import (
    ExtractRequest,
    ExtractResponse,
    SupportedPatternsResponse,
)
from app.tools.key_dates_obligations.service import (
    KeyDatesObligationsError,
    extract_key_dates_and_obligations,
    supported_patterns,
)

router = APIRouter()


@router.get("/patterns", response_model=SupportedPatternsResponse)
def get_supported_patterns() -> SupportedPatternsResponse:
    return supported_patterns()


@router.post("/extract", response_model=ExtractResponse)
def extract(payload: ExtractRequest) -> ExtractResponse:
    try:
        return extract_key_dates_and_obligations(payload)
    except KeyDatesObligationsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
