from __future__ import annotations

import csv
import hashlib
import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.tools.legal_ocr.models import (
    ExistingTextPolicy,
    OcrAnalysisResponse,
    OcrOptions,
    OcrPagePlan,
    OcrPagePlanStatus,
    OcrPageResult,
    OcrRunReport,
)

MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_PDF_PAGES = 1_000
MAX_OCR_PAGES_PER_REQUEST = 500

DISCLAIMER = (
    "OCR is probabilistic character recognition, not legal interpretation. The searchable text layer may contain "
    "recognition errors and must not be treated as an authoritative transcription. Verify material names, dates, "
    "amounts, citations, signatures, and filing content against the page image before legal use."
)


class LegalOcrError(ValueError):
    pass


@dataclass(frozen=True)
class _TesseractWord:
    text: str
    confidence: float


def _open_pdf(pdf_bytes: bytes) -> fitz.Document:
    if not pdf_bytes:
        raise LegalOcrError("PDF file is empty")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise LegalOcrError("PDF exceeds the 100 MB OCR processing limit")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise LegalOcrError("uploaded file does not appear to be a PDF")
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise LegalOcrError("unable to open PDF") from exc
    if document.needs_pass:
        document.close()
        raise LegalOcrError("encrypted/password-protected PDFs are not supported")
    if document.page_count < 1:
        document.close()
        raise LegalOcrError("PDF has no pages")
    if document.page_count > MAX_PDF_PAGES:
        document.close()
        raise LegalOcrError(f"PDF exceeds the {MAX_PDF_PAGES}-page OCR safety limit")
    return document


def _selected_pages(page_count: int, options: OcrOptions) -> set[int]:
    if options.page_numbers is None:
        selected = set(range(1, page_count + 1))
    else:
        out_of_range = sorted(number for number in options.page_numbers if number > page_count)
        if out_of_range:
            preview = ", ".join(str(number) for number in out_of_range[:10])
            suffix = "..." if len(out_of_range) > 10 else ""
            raise LegalOcrError(
                f"page_numbers contains pages outside the PDF ({page_count} pages): {preview}{suffix}"
            )
        selected = set(options.page_numbers)
    if len(selected) > MAX_OCR_PAGES_PER_REQUEST:
        raise LegalOcrError(
            f"OCR request selects {len(selected)} pages; maximum is {MAX_OCR_PAGES_PER_REQUEST} per request"
        )
    return selected


def _tesseract_binary() -> str | None:
    return shutil.which("tesseract")


def installed_languages() -> list[str]:
    binary = _tesseract_binary()
    if binary is None:
        return []
    try:
        result = subprocess.run(
            [binary, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if lines and lines[0].casefold().startswith("list of available languages"):
        lines = lines[1:]
    return sorted(set(lines), key=str.casefold)


def capabilities() -> dict[str, object]:
    languages = installed_languages()
    return {
        "engine": "tesseract",
        "available": _tesseract_binary() is not None,
        "languages": languages,
        "max_pdf_bytes": MAX_PDF_BYTES,
        "max_pdf_pages": MAX_PDF_PAGES,
        "max_ocr_pages_per_request": MAX_OCR_PAGES_PER_REQUEST,
        "dpi_range": [150, 400],
        "psm_range": [1, 13],
        "disclaimer": DISCLAIMER,
    }


def _requested_languages(options: OcrOptions) -> list[str]:
    return [part for part in options.language.split("+") if part]


def _missing_languages(options: OcrOptions) -> list[str]:
    installed = set(installed_languages())
    return [language for language in _requested_languages(options) if language not in installed]


def _page_existing_text_chars(page: fitz.Page) -> int:
    return len("".join(page.get_text("text").split()))


def analyze_pdf_for_ocr(
    pdf_bytes: bytes,
    options: OcrOptions,
    original_filename: str | None = None,
) -> OcrAnalysisResponse:
    document = _open_pdf(pdf_bytes)
    try:
        selected = _selected_pages(document.page_count, options)
        requested = _requested_languages(options)
        missing = _missing_languages(options)
        pages: list[OcrPagePlan] = []
        planned = 0
        existing_count = 0
        warnings: list[str] = []

        if _tesseract_binary() is None:
            warnings.append("Tesseract executable was not found; OCR processing is unavailable until installed.")
        if missing:
            warnings.append("Missing requested Tesseract language data: " + ", ".join(missing))

        for page_number in range(1, document.page_count + 1):
            page = document.load_page(page_number - 1)
            chars = _page_existing_text_chars(page)
            has_text = chars >= options.existing_text_min_chars
            if has_text:
                existing_count += 1

            if page_number not in selected:
                status = OcrPagePlanStatus.SKIP_NOT_SELECTED
            elif has_text and options.existing_text_policy == ExistingTextPolicy.SKIP:
                status = OcrPagePlanStatus.SKIP_EXISTING_TEXT
            elif has_text and options.existing_text_policy == ExistingTextPolicy.ERROR:
                raise LegalOcrError(
                    f"page {page_number} already contains at least {options.existing_text_min_chars} non-whitespace text characters"
                )
            else:
                status = OcrPagePlanStatus.OCR
                planned += 1

            pages.append(
                OcrPagePlan(
                    page_number=page_number,
                    existing_text_chars=chars,
                    status=status,
                )
            )

        if planned == 0:
            warnings.append("No pages are currently planned for OCR with these options.")

        return OcrAnalysisResponse(
            original_filename=original_filename,
            page_count=document.page_count,
            selected_page_count=len(selected),
            pages_planned_for_ocr=planned,
            pages_with_existing_text=existing_count,
            pages=pages,
            tesseract_available=_tesseract_binary() is not None,
            requested_languages=requested,
            missing_languages=missing,
            warnings=warnings,
            disclaimer=DISCLAIMER,
        )
    finally:
        document.close()


def _parse_tsv(tsv_text: str, min_confidence: float = 0.0) -> tuple[list[_TesseractWord], str]:
    words: list[_TesseractWord] = []
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    for row in reader:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        try:
            confidence = float(row.get("conf") or -1)
        except ValueError:
            continue
        if confidence < min_confidence:
            continue
        words.append(_TesseractWord(text=text, confidence=confidence))
    return words, " ".join(word.text for word in words)


def _ocr_page_to_pdf(
    page: fitz.Page,
    options: OcrOptions,
    workdir: Path,
    page_number: int,
) -> tuple[bytes, OcrPageResult]:
    binary = _tesseract_binary()
    if binary is None:
        raise LegalOcrError("Tesseract executable is required for OCR but was not found")

    scale = options.dpi / 72.0
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, annots=True)
    image_path = workdir / f"page-{page_number:05d}.png"
    output_base = workdir / f"page-{page_number:05d}-ocr"
    pixmap.save(image_path)

    command = [
        binary,
        str(image_path),
        str(output_base),
        "-l",
        options.language,
        "--dpi",
        str(options.dpi),
        "--psm",
        str(options.psm),
        "pdf",
        "tsv",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=options.timeout_per_page_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LegalOcrError(
            f"Tesseract timed out while processing page {page_number} after {options.timeout_per_page_seconds} seconds"
        ) from exc
    except OSError as exc:
        raise LegalOcrError(f"unable to start Tesseract for page {page_number}") from exc

    if result.returncode != 0:
        stderr = " ".join(result.stderr.split())[:500]
        raise LegalOcrError(f"Tesseract failed on page {page_number}: {stderr or 'unknown error'}")

    pdf_path = output_base.with_suffix(".pdf")
    tsv_path = output_base.with_suffix(".tsv")
    if not pdf_path.exists() or not tsv_path.exists():
        raise LegalOcrError(f"Tesseract did not produce expected OCR output for page {page_number}")

    words, extracted_text = _parse_tsv(tsv_path.read_text(encoding="utf-8", errors="replace"))
    mean_confidence = None
    if words:
        mean_confidence = round(sum(word.confidence for word in words) / len(words), 2)

    return (
        pdf_path.read_bytes(),
        OcrPageResult(
            page_number=page_number,
            processed=True,
            word_count=len(words),
            mean_confidence=mean_confidence,
            extracted_text=extracted_text,
        ),
    )


def ocr_pdf_bytes(
    pdf_bytes: bytes,
    options: OcrOptions,
    original_filename: str | None = None,
) -> tuple[bytes, OcrRunReport]:
    analysis = analyze_pdf_for_ocr(pdf_bytes, options, original_filename=original_filename)
    if not analysis.tesseract_available:
        raise LegalOcrError("Tesseract executable is required for OCR but was not found")
    if analysis.missing_languages:
        raise LegalOcrError("requested Tesseract language data is not installed: " + ", ".join(analysis.missing_languages))

    source = _open_pdf(pdf_bytes)
    output = fitz.open()
    page_results: list[OcrPageResult] = []
    warnings = list(analysis.warnings)

    try:
        plan_by_page = {item.page_number: item for item in analysis.pages}
        with tempfile.TemporaryDirectory(prefix="lawyer-tools-ocr-") as temp_dir:
            workdir = Path(temp_dir)
            for page_number in range(1, source.page_count + 1):
                plan = plan_by_page[page_number]
                if plan.status != OcrPagePlanStatus.OCR:
                    output.insert_pdf(source, from_page=page_number - 1, to_page=page_number - 1)
                    page_results.append(
                        OcrPageResult(
                            page_number=page_number,
                            processed=False,
                            skipped_reason=plan.status.value,
                        )
                    )
                    continue

                page = source.load_page(page_number - 1)
                ocr_page_bytes, page_result = _ocr_page_to_pdf(page, options, workdir, page_number)
                ocr_page = fitz.open(stream=ocr_page_bytes, filetype="pdf")
                try:
                    if ocr_page.page_count != 1:
                        raise LegalOcrError(f"unexpected Tesseract page count for source page {page_number}")
                    output.insert_pdf(ocr_page)
                finally:
                    ocr_page.close()
                page_results.append(page_result)

        metadata = dict(source.metadata or {})
        metadata["producer"] = "Lawyer Tools OCR (Tesseract + PyMuPDF)"
        output.set_metadata({key: value for key, value in metadata.items() if isinstance(value, str)})
        try:
            toc = source.get_toc(simple=True)
            if toc:
                output.set_toc(toc)
        except Exception:
            warnings.append("Document bookmarks could not be copied to the OCR output.")

        output_bytes = output.tobytes(garbage=4, deflate=True, clean=True)
    finally:
        output.close()
        source.close()

    processed = [item for item in page_results if item.processed]
    confidences = [item.mean_confidence for item in processed if item.mean_confidence is not None]
    mean_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None
    if processed and not any(item.word_count for item in processed):
        warnings.append("OCR completed but no words were recognized on the processed pages.")

    report = OcrRunReport(
        original_filename=original_filename,
        page_count=len(page_results),
        processed_page_count=len(processed),
        skipped_page_count=len(page_results) - len(processed),
        total_word_count=sum(item.word_count for item in processed),
        mean_confidence=mean_confidence,
        output_sha256=hashlib.sha256(output_bytes).hexdigest(),
        pages=page_results,
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
    return output_bytes, report
