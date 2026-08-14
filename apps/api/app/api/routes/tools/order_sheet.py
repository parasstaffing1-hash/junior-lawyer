from fastapi import APIRouter

from app.tools.order_sheet.models import OrderSheetRequest, OrderSheetResponse
from app.tools.order_sheet.service import parse_order_sheet

router = APIRouter()


@router.post("/parse", response_model=OrderSheetResponse)
def parse(request: OrderSheetRequest) -> OrderSheetResponse:
    return parse_order_sheet(request)
