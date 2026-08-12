from fastapi import APIRouter, HTTPException

from app.tools.affidavit.models import (
    AffidavitGenerationRequest,
    AffidavitGenerationResponse,
    AffidavitTemplateSummary,
)
from app.tools.affidavit.service import (
    AffidavitInputError,
    AffidavitTemplateDateError,
    AffidavitTemplateNotFoundError,
    generate_affidavit,
    list_templates,
)

router = APIRouter()


@router.get("/templates", response_model=list[AffidavitTemplateSummary])
def get_templates() -> list[AffidavitTemplateSummary]:
    return list_templates()


@router.post("/generate", response_model=AffidavitGenerationResponse)
def generate(payload: AffidavitGenerationRequest) -> AffidavitGenerationResponse:
    try:
        return generate_affidavit(payload)
    except AffidavitTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (AffidavitTemplateDateError, AffidavitInputError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
