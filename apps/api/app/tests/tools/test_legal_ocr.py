from __future__ import annotations

import shutil
from io import BytesIO

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app
from app.tools.legal_ocr.models import ExistingTextPolicy, OcrOptions
from app.tools.legal_ocr.service import LegalOcrError, analyze_pdf_for_ocr, capabilities, ocr_pdf_bytes

client = TestClient(app)
TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


def _font(size: int = 48):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _scan_image(text: str) -> bytes:
    image = Image.new("RGB", (1654, 2339), "white")
    draw = ImageDraw.Draw(image)
    draw.multiline_text((120, 160), text, fill="black", font=_font(), spacing=24)
    stream = BytesIO()
    image.save(stream, format="PNG", dpi=(200, 200))
    return stream.getvalue()


def _make_scanned_pdf(text: str = "LEGAL NOTICE\nPayment is due on 15 August 2026") -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=_scan_image(text))
    data = document.tobytes(deflate=True)
    document.close()
    return data


def _make_text_pdf(text: str = "This page already contains searchable legal text.") -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 90), text, fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def _make_mixed_pdf() -> bytes:
    text_doc = fitz.open(stream=_make_text_pdf("SEARCHABLE CONTRACT PAGE"), filetype="pdf")
    scan_doc = fitz.open(stream=_make_scanned_pdf("SCANNED EXHIBIT\nInvoice 125000"), filetype="pdf")
    out = fitz.open()
    out.insert_pdf(text_doc)
    out.insert_pdf(scan_doc)
    data = out.tobytes(deflate=True)
    out.close()
    text_doc.close()
    scan_doc.close()
    return data


def test_analysis_marks_scanned_page_for_ocr() -> None:
    result = analyze_pdf_for_ocr(_make_scanned_pdf(), OcrOptions(language="eng"), "scan.pdf")
    assert result.page_count == 1
    assert result.pages_planned_for_ocr == 1
    assert result.pages[0].status.value == "ocr"
    assert result.pages[0].existing_text_chars == 0


def test_analysis_skips_existing_searchable_text_by_default() -> None:
    result = analyze_pdf_for_ocr(_make_text_pdf(), OcrOptions(existing_text_min_chars=10))
    assert result.pages_planned_for_ocr == 0
    assert result.pages_with_existing_text == 1
    assert result.pages[0].status.value == "skip_existing_text"


def test_analysis_can_force_existing_text_page() -> None:
    result = analyze_pdf_for_ocr(
        _make_text_pdf(),
        OcrOptions(existing_text_policy=ExistingTextPolicy.FORCE, existing_text_min_chars=10),
    )
    assert result.pages_planned_for_ocr == 1
    assert result.pages[0].status.value == "ocr"


def test_error_policy_rejects_existing_text() -> None:
    with pytest.raises(LegalOcrError, match="already contains"):
        analyze_pdf_for_ocr(
            _make_text_pdf(),
            OcrOptions(existing_text_policy=ExistingTextPolicy.ERROR, existing_text_min_chars=10),
        )


def test_page_selection_is_one_based_and_preserves_other_pages() -> None:
    result = analyze_pdf_for_ocr(_make_mixed_pdf(), OcrOptions(page_numbers=[2]))
    assert [page.status.value for page in result.pages] == ["skip_not_selected", "ocr"]


def test_unknown_page_is_rejected() -> None:
    with pytest.raises(LegalOcrError, match="outside the PDF"):
        analyze_pdf_for_ocr(_make_scanned_pdf(), OcrOptions(page_numbers=[2]))


def test_invalid_file_is_rejected() -> None:
    with pytest.raises(LegalOcrError, match="does not appear to be a PDF"):
        analyze_pdf_for_ocr(b"not a pdf", OcrOptions())


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract is not installed")
def test_ocr_creates_searchable_pdf_and_report() -> None:
    output, report = ocr_pdf_bytes(_make_scanned_pdf(), OcrOptions(language="eng", dpi=200))
    assert output.startswith(b"%PDF-")
    assert report.processed_page_count == 1
    assert report.total_word_count >= 4
    assert report.mean_confidence is not None

    document = fitz.open(stream=output, filetype="pdf")
    try:
        extracted = document[0].get_text("text").upper()
        assert "LEGAL" in extracted
        assert "NOTICE" in extracted
        assert "AUGUST" in extracted
    finally:
        document.close()


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract is not installed")
def test_mixed_pdf_only_ocrs_scanned_page_by_default() -> None:
    output, report = ocr_pdf_bytes(_make_mixed_pdf(), OcrOptions(language="eng", dpi=200, existing_text_min_chars=10))
    assert report.processed_page_count == 1
    assert report.skipped_page_count == 1
    assert report.pages[0].skipped_reason == "skip_existing_text"

    document = fitz.open(stream=output, filetype="pdf")
    try:
        assert "SEARCHABLE CONTRACT PAGE" in document[0].get_text("text")
        assert "SCANNED" in document[1].get_text("text").upper()
    finally:
        document.close()


def test_capabilities_endpoint_reports_engine() -> None:
    response = client.get("/api/v1/tools/legal-ocr/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["engine"] == "tesseract"
    assert "eng" in payload["languages"] or not payload["available"]


def test_analyze_api_accepts_scan() -> None:
    response = client.post(
        "/api/v1/tools/legal-ocr/analyze",
        files={"file": ("scan.pdf", _make_scanned_pdf(), "application/pdf")},
        data={"options_json": '{"language":"eng","dpi":200}'},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["original_filename"] == "scan.pdf"
    assert payload["pages_planned_for_ocr"] == 1


@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract is not installed")
def test_process_api_returns_searchable_pdf() -> None:
    response = client.post(
        "/api/v1/tools/legal-ocr/process",
        files={"file": ("scan.pdf", _make_scanned_pdf(), "application/pdf")},
        data={"options_json": '{"language":"eng","dpi":200}'},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["x-ocr-processed-pages"] == "1"
    assert int(response.headers["x-ocr-word-count"]) >= 4

    document = fitz.open(stream=response.content, filetype="pdf")
    try:
        assert "LEGAL" in document[0].get_text("text").upper()
    finally:
        document.close()


def test_options_reject_duplicate_pages() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        OcrOptions(page_numbers=[1, 1])
