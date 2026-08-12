import json
import io
import zipfile
from pathlib import PurePosixPath

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.core.config import settings
from app.core.uploads import UploadTooLargeError, read_upload_limited
from app.tools.legal_document_parser.models import ParseOptions, ParseResponse
from app.tools.legal_document_parser.service import (
    LegalDocumentParserError,
    parse_legal_document,
    supported_formats,
)

router = APIRouter()


def _validate_zip_safety(data: bytes) -> None:
    if not data.startswith(b"PK\x03\x04"):
        return
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 2_000:
                raise HTTPException(status_code=422, detail="DOCX archive contains too many ZIP entries")
            total_uncompressed = 0
            for info in infos:
                member = PurePosixPath(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise HTTPException(status_code=422, detail="DOCX archive contains an unsafe member path")
                if info.file_size > 20 * 1024 * 1024:
                    raise HTTPException(status_code=422, detail="DOCX archive contains an oversized member")
                total_uncompressed += info.file_size
                if total_uncompressed > 50 * 1024 * 1024:
                    raise HTTPException(status_code=422, detail="DOCX archive expands beyond the safety limit")
                if info.compress_size and info.file_size > info.compress_size * 1_000:
                    raise HTTPException(status_code=422, detail="DOCX archive has an unsafe compression ratio")
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail="invalid ZIP-based document") from exc


def _parse_options(options_json: str) -> ParseOptions:
    try:
        payload = json.loads(options_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="options_json must be valid JSON") from exc
    try:
        return ParseOptions.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.get("/formats")
def formats() -> list[dict[str, object]]:
    return supported_formats()


@router.post("/parse", response_model=ParseResponse)
async def parse_document(
    file: UploadFile = File(...),
    options_json: str = Form(default="{}"),
) -> ParseResponse:
    options = _parse_options(options_json)
    try:
        data = await read_upload_limited(file, settings.max_upload_mb * 1024 * 1024)
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    _validate_zip_safety(data)
    try:
        return parse_legal_document(data, options, original_filename=file.filename)
    except LegalDocumentParserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
