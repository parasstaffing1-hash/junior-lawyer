from fastapi import APIRouter, HTTPException

from app.tools.legal_citation.models import (
    CitationExtractRequest,
    CitationExtractResponse,
    CitationFormatRequest,
    CitationFormatResponse,
)
from app.tools.legal_citation.service import LegalCitationError, extract_citations, format_citation

router = APIRouter()


@router.post("/format", response_model=CitationFormatResponse)
def format_legal_citation(payload: CitationFormatRequest) -> CitationFormatResponse:
    try:
        return format_citation(payload)
    except LegalCitationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/extract", response_model=CitationExtractResponse)
def extract_legal_citations(payload: CitationExtractRequest) -> CitationExtractResponse:
    try:
        return extract_citations(payload)
    except LegalCitationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
