from fastapi import APIRouter, HTTPException, status

from app.tools.cheque_timeline.models import ChequeTimelineRequest, ChequeTimelineResponse
from app.tools.cheque_timeline.service import ChequeTimelineInputError, calculate_cheque_timeline

router = APIRouter()


@router.post("/calculate", response_model=ChequeTimelineResponse)
def calculate(request: ChequeTimelineRequest) -> ChequeTimelineResponse:
    try:
        return calculate_cheque_timeline(request)
    except ChequeTimelineInputError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
