from fastapi import APIRouter, HTTPException, Query

from app.tools.client_matter_intake.models import (
    ClientMatterIntakeRequest,
    ClientMatterIntakeResponse,
    IntakeTemplateSummary,
)
from app.tools.client_matter_intake.service import (
    IntakeInputError,
    IntakeTemplateDateError,
    IntakeTemplateNotFoundError,
    generate_intake,
    list_templates,
)

router = APIRouter()


@router.get("/templates", response_model=list[IntakeTemplateSummary])
def get_templates(
    matter_type: str | None = Query(default=None, min_length=1, max_length=120),
    client_type: str | None = Query(default=None, min_length=1, max_length=120),
) -> list[IntakeTemplateSummary]:
    return list_templates(matter_type=matter_type, client_type=client_type)


@router.post("/generate", response_model=ClientMatterIntakeResponse)
def generate(payload: ClientMatterIntakeRequest) -> ClientMatterIntakeResponse:
    try:
        return generate_intake(payload)
    except IntakeTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (IntakeTemplateDateError, IntakeInputError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
