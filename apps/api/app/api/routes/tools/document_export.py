import json
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from app.tools.document_export.models import (
    DocumentExportPreview,
    DocumentExportRequest,
    ExportFormat,
)
from app.tools.document_export.service import (
    DocumentExportError,
    generate_export,
    preview_export,
)

router = APIRouter()


@router.get("/formats")
def formats() -> dict[str, object]:
    return {
        "formats": [item.value for item in ExportFormat],
        "source_types": [
            "legal_notice",
            "affidavit",
            "case_timeline",
            "evidence_index",
            "legal_checklist",
            "client_intake",
            "generic",
        ],
        "notes": [
            "DOCX page count is not reported because pagination depends on the rendering engine.",
            "PDF uses deterministic server-side rendering and reports the validated page count.",
        ],
    }


@router.post("/preview", response_model=DocumentExportPreview)
def preview(payload: DocumentExportRequest) -> DocumentExportPreview:
    try:
        return preview_export(payload)
    except DocumentExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/generate")
def generate(payload: DocumentExportRequest) -> Response:
    try:
        content, info = generate_export(payload)
    except DocumentExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(info.filename)}",
        "X-Document-SHA256": info.sha256,
        "X-Document-Size": str(info.size_bytes),
        "X-Document-Warnings": json.dumps(info.warnings, separators=(",", ":")),
    }
    if info.page_count is not None:
        headers["X-Document-Pages"] = str(info.page_count)
    return Response(content=content, media_type=info.media_type, headers=headers)
