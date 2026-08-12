from fastapi import APIRouter, HTTPException

from app.tools.legal_notice.models import (
    LegalNoticeGenerationRequest,
    LegalNoticeGenerationResponse,
    LegalNoticeTemplateSummary,
)
from app.tools.legal_notice.service import (
    LegalNoticeInputError,
    LegalNoticeTemplateDateError,
    LegalNoticeTemplateNotFoundError,
    generate_legal_notice,
    list_templates,
)

router = APIRouter()


@router.get("/templates", response_model=list[LegalNoticeTemplateSummary])
def get_templates() -> list[LegalNoticeTemplateSummary]:
    return list_templates()


@router.post("/generate", response_model=LegalNoticeGenerationResponse)
def generate(payload: LegalNoticeGenerationRequest) -> LegalNoticeGenerationResponse:
    try:
        return generate_legal_notice(payload)
    except LegalNoticeTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (LegalNoticeTemplateDateError, LegalNoticeInputError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
