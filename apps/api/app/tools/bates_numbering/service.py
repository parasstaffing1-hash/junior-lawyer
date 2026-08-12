from __future__ import annotations

from dataclasses import dataclass

import fitz

from app.tools.bates_numbering.models import (
    BatesAssignment,
    BatesNumberingOptions,
    BatesPosition,
    BatesPreviewResponse,
    CollisionPolicy,
)


DISCLAIMER = (
    "Bates numbers are applied deterministically to the selected PDF pages. "
    "The tool does not determine discovery obligations, filing rules, confidentiality, privilege, "
    "or whether a numbering format is accepted by a court, tribunal, regulator, or counterparty. "
    "Verify the final PDF visually before production, service, filing, or disclosure."
)
MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_PAGES = 20_000


class BatesNumberingError(ValueError):
    pass


class BatesCollisionError(BatesNumberingError):
    pass


@dataclass(frozen=True)
class _StampGeometry:
    point: fitz.Point
    bbox: fitz.Rect


def _open_pdf(pdf_bytes: bytes) -> fitz.Document:
    if not pdf_bytes:
        raise BatesNumberingError("PDF file is empty")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise BatesNumberingError("PDF exceeds the 100 MB processing limit")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise BatesNumberingError("uploaded file does not appear to be a PDF")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several format-specific exception types.
        raise BatesNumberingError("unable to open PDF") from exc

    if document.needs_pass:
        document.close()
        raise BatesNumberingError("encrypted/password-protected PDFs are not supported")
    if document.page_count < 1:
        document.close()
        raise BatesNumberingError("PDF has no pages")
    if document.page_count > MAX_PAGES:
        document.close()
        raise BatesNumberingError(f"PDF exceeds the {MAX_PAGES}-page processing limit")
    return document


def _selected_pages(page_count: int, options: BatesNumberingOptions) -> list[int]:
    if options.page_numbers is None:
        return list(range(1, page_count + 1))

    out_of_range = sorted(number for number in options.page_numbers if number > page_count)
    if out_of_range:
        preview = ", ".join(str(number) for number in out_of_range[:10])
        suffix = "..." if len(out_of_range) > 10 else ""
        raise BatesNumberingError(
            f"page_numbers contains pages outside the PDF ({page_count} pages): {preview}{suffix}"
        )
    return sorted(options.page_numbers)


def _format_number(value: int, options: BatesNumberingOptions) -> str:
    numeric = str(value).zfill(options.digits)
    return f"{options.prefix}{numeric}{options.suffix}"


def _geometry(page: fitz.Page, label: str, options: BatesNumberingOptions) -> _StampGeometry:
    page_rect = page.rect
    text_width = fitz.get_text_length(label, fontname="helv", fontsize=options.font_size)
    text_height = options.font_size * 1.25

    left_x = page_rect.x0 + options.margin_x
    center_x = page_rect.x0 + (page_rect.width - text_width) / 2
    right_x = page_rect.x1 - options.margin_x - text_width

    top_baseline = page_rect.y0 + options.margin_y + options.font_size
    bottom_baseline = page_rect.y1 - options.margin_y

    if options.position == BatesPosition.TOP_LEFT:
        x, y = left_x, top_baseline
    elif options.position == BatesPosition.TOP_CENTER:
        x, y = center_x, top_baseline
    elif options.position == BatesPosition.TOP_RIGHT:
        x, y = right_x, top_baseline
    elif options.position == BatesPosition.BOTTOM_LEFT:
        x, y = left_x, bottom_baseline
    elif options.position == BatesPosition.BOTTOM_CENTER:
        x, y = center_x, bottom_baseline
    else:
        x, y = right_x, bottom_baseline

    bbox = fitz.Rect(x - 1, y - text_height, x + text_width + 1, y + 2)
    if bbox.x0 < page_rect.x0 or bbox.y0 < page_rect.y0 or bbox.x1 > page_rect.x1 or bbox.y1 > page_rect.y1:
        raise BatesNumberingError(
            f"Bates label does not fit page {page.number + 1}; reduce font/margins/prefix/suffix"
        )
    return _StampGeometry(point=fitz.Point(x, y), bbox=bbox)


def _has_text_collision(page: fitz.Page, stamp_bbox: fitz.Rect) -> bool:
    # get_text("blocks") returns coarse rectangles for text/image blocks. We only treat text blocks
    # as collisions and deliberately use rectangle intersection instead of attempting semantic analysis.
    for block in page.get_text("blocks"):
        if len(block) < 7:
            continue
        x0, y0, x1, y1, text, _block_no, block_type = block[:7]
        if block_type != 0 or not str(text).strip():
            continue
        block_rect = fitz.Rect(float(x0), float(y0), float(x1), float(y1))
        if block_rect.intersects(stamp_bbox):
            intersection = block_rect & stamp_bbox
            if not intersection.is_empty and intersection.get_area() > 0:
                return True
    return False


def _build_assignments(
    document: fitz.Document,
    options: BatesNumberingOptions,
) -> tuple[list[BatesAssignment], dict[int, _StampGeometry], list[str]]:
    selected = _selected_pages(document.page_count, options)
    assignments: list[BatesAssignment] = []
    geometry_by_page: dict[int, _StampGeometry] = {}
    warnings: list[str] = []

    current_number = options.start_number
    for page_number in selected:
        label = _format_number(current_number, options)
        page = document.load_page(page_number - 1)
        geometry = _geometry(page, label, options)
        collision = _has_text_collision(page, geometry.bbox)
        if collision and options.collision_policy == CollisionPolicy.ERROR:
            raise BatesCollisionError(
                f"possible existing-text collision on page {page_number} at {options.position.value}"
            )
        if collision and options.collision_policy == CollisionPolicy.WARN:
            warnings.append(
                f"Possible existing-text collision on page {page_number} at {options.position.value}."
            )
        assignments.append(
            BatesAssignment(
                page_number=page_number,
                bates_number=label,
                collision_detected=collision,
            )
        )
        geometry_by_page[page_number] = geometry
        current_number += options.increment

    return assignments, geometry_by_page, warnings


def preview_bates_numbering(
    pdf_bytes: bytes,
    options: BatesNumberingOptions,
    original_filename: str | None = None,
) -> BatesPreviewResponse:
    document = _open_pdf(pdf_bytes)
    try:
        assignments, _geometry, warnings = _build_assignments(document, options)
        collision_pages = [item.page_number for item in assignments if item.collision_detected]
        return BatesPreviewResponse(
            original_filename=original_filename,
            page_count=document.page_count,
            stamped_page_count=len(assignments),
            skipped_page_count=document.page_count - len(assignments),
            first_bates_number=assignments[0].bates_number if assignments else None,
            last_bates_number=assignments[-1].bates_number if assignments else None,
            assignments=assignments,
            collision_pages=collision_pages,
            warnings=warnings,
            disclaimer=DISCLAIMER,
        )
    finally:
        document.close()


def stamp_pdf_bytes(
    pdf_bytes: bytes,
    options: BatesNumberingOptions,
) -> tuple[bytes, BatesPreviewResponse]:
    document = _open_pdf(pdf_bytes)
    try:
        assignments, geometry_by_page, warnings = _build_assignments(document, options)
        for assignment in assignments:
            page = document.load_page(assignment.page_number - 1)
            geometry = geometry_by_page[assignment.page_number]
            page.insert_text(
                geometry.point,
                assignment.bates_number,
                fontname="helv",
                fontsize=options.font_size,
                overlay=True,
            )

        try:
            output = document.tobytes(garbage=4, deflate=True, clean=True)
        except Exception as exc:
            raise BatesNumberingError("unable to save stamped PDF") from exc

        report = BatesPreviewResponse(
            original_filename=None,
            page_count=document.page_count,
            stamped_page_count=len(assignments),
            skipped_page_count=document.page_count - len(assignments),
            first_bates_number=assignments[0].bates_number if assignments else None,
            last_bates_number=assignments[-1].bates_number if assignments else None,
            assignments=assignments,
            collision_pages=[item.page_number for item in assignments if item.collision_detected],
            warnings=warnings,
            disclaimer=DISCLAIMER,
        )
        return output, report
    finally:
        document.close()
