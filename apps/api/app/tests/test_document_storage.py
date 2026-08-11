import pytest
from fastapi import HTTPException

from app.services.documents.storage import sanitize_filename, validate_extension, validate_staged_content


def test_sanitize_filename_removes_path_and_unsafe_symbols() -> None:
    assert sanitize_filename("../../My आदेश #1.pdf") == "My आदेश _1.pdf"


def test_validate_extension_is_case_insensitive() -> None:
    extension, mime = validate_extension("Order.PDF")
    assert extension == ".pdf"
    assert mime == "application/pdf"


def test_unsupported_document_type_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_extension("payload.exe")
    assert exc.value.status_code == 415


def test_signature_validation_accepts_real_pdf_header(tmp_path) -> None:
    path = tmp_path / "order.pdf"
    path.write_bytes(b"%PDF-1.7\n% deterministic test")
    validate_staged_content(path, ".pdf")
    assert path.exists()


def test_signature_validation_rejects_spoofed_pdf(tmp_path) -> None:
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"MZ this is not a pdf")
    with pytest.raises(HTTPException) as exc:
        validate_staged_content(path, ".pdf")
    assert exc.value.status_code == 415
    assert not path.exists()


def test_storage_key_rejects_traversal() -> None:
    from app.services.documents.storage import _safe_relative_key
    with pytest.raises(RuntimeError):
        _safe_relative_key("../../secret.txt")
