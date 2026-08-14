from fastapi import APIRouter, HTTPException, status

from app.tools.maintenance_estimate.models import (
    MaintenanceEstimateRequest,
    MaintenanceEstimateResponse,
)
from app.tools.maintenance_estimate.service import MaintenanceInputError, estimate_maintenance

router = APIRouter()


@router.post("/estimate", response_model=MaintenanceEstimateResponse)
def estimate(request: MaintenanceEstimateRequest) -> MaintenanceEstimateResponse:
    try:
        return estimate_maintenance(request)
    except MaintenanceInputError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
