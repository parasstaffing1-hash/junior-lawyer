from fastapi import APIRouter, HTTPException

from app.tools.case_timeline.models import CaseTimelineRequest, CaseTimelineResponse
from app.tools.case_timeline.service import CaseTimelineError, generate_case_timeline

router = APIRouter()


@router.post("/generate", response_model=CaseTimelineResponse)
def generate(payload: CaseTimelineRequest) -> CaseTimelineResponse:
    try:
        return generate_case_timeline(payload)
    except CaseTimelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
