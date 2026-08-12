from fastapi import APIRouter, HTTPException, Query

from app.tools.legal_checklist.models import (
    ChecklistTemplateSummary,
    LegalChecklistRequest,
    LegalChecklistResponse,
)
from app.tools.legal_checklist.service import (
    LegalChecklistInputError,
    LegalChecklistTemplateDateError,
    LegalChecklistTemplateNotFoundError,
    evaluate_checklist,
    list_templates,
)

router = APIRouter()


@router.get("/templates", response_model=list[ChecklistTemplateSummary])
def get_templates(
    matter_type: str | None = Query(default=None, min_length=1, max_length=120),
) -> list[ChecklistTemplateSummary]:
    return list_templates(matter_type=matter_type)


@router.post("/evaluate", response_model=LegalChecklistResponse)
def evaluate(payload: LegalChecklistRequest) -> LegalChecklistResponse:
    try:
        return evaluate_checklist(payload)
    except LegalChecklistTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (LegalChecklistTemplateDateError, LegalChecklistInputError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
