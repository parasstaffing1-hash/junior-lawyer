import json

import fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tools.bates_numbering.models import BatesNumberingOptions
from app.tools.bates_numbering.service import (
    BatesCollisionError,
    BatesNumberingError,
    preview_bates_numbering,
    stamp_pdf_bytes,
)

client = TestClient(app)


def _make_pdf(page_count: int = 3, *, footer_collision: bool = False) -> bytes:
    document = fitz.open()
    for index in range(page_count):
        page = document.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page content {index + 1}", fontsize=11)
        if footer_collision and index == 0:
            page.insert_text((475, 818), "Existing footer", fontsize=9)
    output = document.tobytes()
    document.close()
    return output


def _page_texts(pdf_bytes: bytes) -> list[str]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [document.load_page(i).get_text() for i in range(document.page_count)]
    finally:
        document.close()


def test_preview_numbers_every_page_by_default() -> None:
    result = preview_bates_numbering(
        _make_pdf(3),
        BatesNumberingOptions(prefix="CASE-", start_number=42, digits=5),
        original_filename="bundle.pdf",
    )
    assert result.page_count == 3
    assert result.stamped_page_count == 3
    assert result.first_bates_number == "CASE-00042"
    assert result.last_bates_number == "CASE-00044"
    assert [item.page_number for item in result.assignments] == [1, 2, 3]
    assert result.original_filename == "bundle.pdf"


def test_selected_pages_are_numbered_in_document_order() -> None:
    result = preview_bates_numbering(
        _make_pdf(4),
        BatesNumberingOptions(
            prefix="EX-",
            suffix="-A",
            start_number=10,
            digits=3,
            increment=5,
            page_numbers=[4, 2],
        ),
    )
    assert [(item.page_number, item.bates_number) for item in result.assignments] == [
        (2, "EX-010-A"),
        (4, "EX-015-A"),
    ]
    assert result.skipped_page_count == 2


def test_stamp_writes_searchable_bates_text_to_selected_pages() -> None:
    output, report = stamp_pdf_bytes(
        _make_pdf(3),
        BatesNumberingOptions(prefix="DOC-", digits=4, page_numbers=[1, 3]),
    )
    texts = _page_texts(output)
    assert "DOC-0001" in texts[0]
    assert "DOC-0001" not in texts[1]
    assert "DOC-0002" in texts[2]
    assert report.stamped_page_count == 2


def test_top_left_position_is_inside_page() -> None:
    output, _report = stamp_pdf_bytes(
        _make_pdf(1),
        BatesNumberingOptions(prefix="TL-", position="top_left", margin_x=20, margin_y=20),
    )
    assert "TL-000001" in _page_texts(output)[0]


def test_out_of_range_page_is_rejected() -> None:
    with pytest.raises(BatesNumberingError, match="outside the PDF"):
        preview_bates_numbering(
            _make_pdf(2),
            BatesNumberingOptions(page_numbers=[3]),
        )


def test_non_pdf_input_is_rejected() -> None:
    with pytest.raises(BatesNumberingError, match="does not appear to be a PDF"):
        preview_bates_numbering(b"not a pdf", BatesNumberingOptions())


def test_collision_warning_is_reported() -> None:
    result = preview_bates_numbering(
        _make_pdf(1, footer_collision=True),
        BatesNumberingOptions(prefix="COLLIDE-", collision_policy="warn"),
    )
    assert result.collision_pages == [1]
    assert result.assignments[0].collision_detected is True
    assert any("collision" in warning.lower() for warning in result.warnings)


def test_collision_policy_error_blocks_stamping() -> None:
    with pytest.raises(BatesCollisionError, match="collision"):
        stamp_pdf_bytes(
            _make_pdf(1, footer_collision=True),
            BatesNumberingOptions(prefix="COLLIDE-", collision_policy="error"),
        )


def test_preview_api_accepts_pdf_and_options_json() -> None:
    response = client.post(
        "/api/v1/tools/bates-numbering/preview",
        files={"file": ("case.pdf", _make_pdf(2), "application/pdf")},
        data={"options_json": json.dumps({"prefix": "API-", "digits": 3})},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["original_filename"] == "case.pdf"
    assert payload["first_bates_number"] == "API-001"
    assert payload["last_bates_number"] == "API-002"


def test_stamp_api_returns_pdf_with_audit_headers() -> None:
    response = client.post(
        "/api/v1/tools/bates-numbering/stamp",
        files={"file": ("case.pdf", _make_pdf(2), "application/pdf")},
        data={"options_json": json.dumps({"prefix": "API-", "start_number": 7, "digits": 4})},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["x-bates-first"] == "API-0007"
    assert response.headers["x-bates-last"] == "API-0008"
    assert response.headers["x-bates-stamped-pages"] == "2"
    assert 'filename="case-bates.pdf"' in response.headers["content-disposition"]
    assert "API-0007" in _page_texts(response.content)[0]
    assert "API-0008" in _page_texts(response.content)[1]
