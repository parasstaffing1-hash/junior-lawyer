import json
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.tools.bates_numbering.models import BatesNumberingOptions, BatesPreviewResponse
from app.core.config import settings
from app.core.uploads import UploadTooLargeError, read_upload_limited
from app.tools.bates_numbering.service import (
    BatesCollisionError,
    BatesNumberingError,
    preview_bates_numbering,
    stamp_pdf_bytes,
)

router = APIRouter()


def _parse_options(options_json: str) -> BatesNumberingOptions:
    try:
        payload = json.loads(options_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="options_json must be valid JSON") from exc
    try:
        return BatesNumberingOptions.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


def _safe_output_name(filename: str | None) -> str:
    if not filename:
        return "bates-numbered.pdf"
    stem = Path(filename).stem.strip() or "document"
    safe = "".join(char for char in stem if char.isalnum() or char in {"-", "_", " "}).strip()
    return f"{safe or 'document'}-bates.pdf"


@router.post("/preview", response_model=BatesPreviewResponse)
async def preview(
    file: UploadFile = File(...),
    options_json: str = Form(default="{}"),
) -> BatesPreviewResponse:
    options = _parse_options(options_json)
    try:
        pdf_bytes = await read_upload_limited(file, settings.max_upload_mb * 1024 * 1024)
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    try:
        return preview_bates_numbering(pdf_bytes, options, original_filename=file.filename)
    except BatesCollisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BatesNumberingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/stamp",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def stamp(
    file: UploadFile = File(...),
    options_json: str = Form(default="{}"),
) -> StreamingResponse:
    options = _parse_options(options_json)
    try:
        pdf_bytes = await read_upload_limited(file, settings.max_upload_mb * 1024 * 1024)
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    try:
        output, report = stamp_pdf_bytes(pdf_bytes, options)
    except BatesCollisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BatesNumberingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    headers = {
        "Content-Disposition": f'attachment; filename="{_safe_output_name(file.filename)}"',
        "X-Bates-Stamped-Pages": str(report.stamped_page_count),
        "X-Bates-Warnings": str(len(report.warnings)),
    }
    if report.first_bates_number is not None:
        headers["X-Bates-First"] = report.first_bates_number
    if report.last_bates_number is not None:
        headers["X-Bates-Last"] = report.last_bates_number

    return StreamingResponse(BytesIO(output), media_type="application/pdf", headers=headers)
