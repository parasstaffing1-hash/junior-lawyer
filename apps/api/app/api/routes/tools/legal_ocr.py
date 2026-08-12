import json
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError

from app.core.config import settings
from app.core.uploads import UploadTooLargeError, read_upload_limited
from app.tools.legal_ocr.models import OcrAnalysisResponse, OcrOptions
from app.tools.legal_ocr.service import (
    LegalOcrError,
    analyze_pdf_for_ocr,
    capabilities,
    ocr_pdf_bytes,
)

router = APIRouter()


def _parse_options(options_json: str) -> OcrOptions:
    try:
        payload = json.loads(options_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="options_json must be valid JSON") from exc
    try:
        return OcrOptions.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.get("/capabilities")
def get_capabilities() -> dict[str, object]:
    return capabilities()


@router.post("/analyze", response_model=OcrAnalysisResponse)
async def analyze(
    file: UploadFile = File(...),
    options_json: str = Form(default="{}"),
) -> OcrAnalysisResponse:
    options = _parse_options(options_json)
    try:
        data = await read_upload_limited(file, settings.max_upload_mb * 1024 * 1024)
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    try:
        return analyze_pdf_for_ocr(data, options, original_filename=file.filename)
    except LegalOcrError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/process")
async def process(
    file: UploadFile = File(...),
    options_json: str = Form(default="{}"),
) -> Response:
    options = _parse_options(options_json)
    try:
        data = await read_upload_limited(file, settings.max_upload_mb * 1024 * 1024)
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    try:
        output_bytes, report = ocr_pdf_bytes(data, options, original_filename=file.filename)
    except LegalOcrError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    original = file.filename or "document.pdf"
    stem = original.rsplit(".", 1)[0] if "." in original else original
    download_name = f"{stem}-searchable.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{quote(download_name)}"',
        "X-OCR-Processed-Pages": str(report.processed_page_count),
        "X-OCR-Skipped-Pages": str(report.skipped_page_count),
        "X-OCR-Word-Count": str(report.total_word_count),
        "X-OCR-Mean-Confidence": "" if report.mean_confidence is None else str(report.mean_confidence),
        "X-OCR-SHA256": report.output_sha256,
    }
    return Response(content=output_bytes, media_type="application/pdf", headers=headers)
