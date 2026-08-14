from fastapi import APIRouter

from app.tools.cause_list_match.models import CauseListMatchRequest, CauseListMatchResponse
from app.tools.cause_list_match.service import match_cause_list

router = APIRouter()


@router.post("/match", response_model=CauseListMatchResponse)
def match(request: CauseListMatchRequest) -> CauseListMatchResponse:
    return match_cause_list(request)
