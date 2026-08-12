from fastapi import APIRouter

from app.tools.legal_deadline.models import LegalDeadlineRequest, LegalDeadlineResponse
from app.tools.legal_deadline.service import calculate_deadline

router = APIRouter()


@router.post("/calculate", response_model=LegalDeadlineResponse)
def calculate_legal_deadline(payload: LegalDeadlineRequest) -> LegalDeadlineResponse:
    return calculate_deadline(payload)
