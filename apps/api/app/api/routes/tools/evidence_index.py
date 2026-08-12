from fastapi import APIRouter, HTTPException

from app.tools.evidence_index.models import EvidenceIndexRequest, EvidenceIndexResponse
from app.tools.evidence_index.service import EvidenceIndexError, generate_evidence_index

router = APIRouter()


@router.post("/generate", response_model=EvidenceIndexResponse)
def generate(payload: EvidenceIndexRequest) -> EvidenceIndexResponse:
    try:
        return generate_evidence_index(payload)
    except EvidenceIndexError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
