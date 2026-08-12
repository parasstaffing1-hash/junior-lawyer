from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from statistics import median
from zipfile import BadZipFile, ZipFile

import fitz
from docx import Document
from docx.document import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P

from app.tools.legal_document_parser.models import (
    BlockType,
    DocumentFormat,
    DocumentMetadata,
    HeadingMethod,
    ParseOptions,
    ParsedBlock,
    ParsedHeading,
    ParsedPage,
    ParsedTable,
    ParseResponse,
)

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 3_000
MAX_DOCX_UNCOMPRESSED_BYTES = 150 * 1024 * 1024
MAX_DOCX_ZIP_RATIO = 250

DISCLAIMER = (
    "This parser extracts document content deterministically and does not verify legal accuracy, "
    "authenticity, privilege, completeness, or filing compliance. PDF heading detection is heuristic. "
    "Scanned/image-only PDFs require a separate OCR step."
)


class LegalDocumentParserError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’.-]\w+)*\b", text, flags=re.UNICODE))


def _clean_block_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r", "").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _parse_pdf_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith("D:"):
        value = value[2:]
    match = re.match(r"(?P<year>\d{4})(?P<month>\d{2})?(?P<day>\d{2})?(?P<hour>\d{2})?(?P<minute>\d{2})?(?P<second>\d{2})?", value)
    if not match:
        return None
    try:
        parts = match.groupdict(default="")
        return datetime(
            int(parts["year"]),
            int(parts["month"] or 1),
            int(parts["day"] or 1),
            int(parts["hour"] or 0),
            int(parts["minute"] or 0),
            int(parts["second"] or 0),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None


def _append_piece(parts: list[str], piece: str, current_length: int) -> tuple[int, int, int]:
    if parts:
        parts.append("\n\n")
        current_length += 2
    start = current_length
    parts.append(piece)
    end = start + len(piece)
    return start, end, end


def _detect_format(data: bytes) -> DocumentFormat:
    if data.startswith(b"%PDF-"):
        return DocumentFormat.PDF
    if data.startswith(b"PK"):
        try:
            with ZipFile(BytesIO(data)) as archive:
                names = {name.casefold() for name in archive.namelist()}
                if "word/document.xml" in names and "[content_types].xml" in names:
                    return DocumentFormat.DOCX
        except BadZipFile:
            pass
    raise LegalDocumentParserError("Unsupported file. Upload a valid PDF or DOCX document.")


def _validate_size(data: bytes) -> None:
    if not data:
        raise LegalDocumentParserError("The uploaded file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise LegalDocumentParserError(f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB safety limit.")


def _validate_docx_archive(data: bytes) -> None:
    try:
        with ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            total_uncompressed = sum(item.file_size for item in infos)
            total_compressed = sum(max(item.compress_size, 1) for item in infos)
            if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise LegalDocumentParserError("DOCX uncompressed content exceeds the safety limit.")
            if total_uncompressed / total_compressed > MAX_DOCX_ZIP_RATIO:
                raise LegalDocumentParserError("DOCX compression ratio exceeds the safety limit.")
            if any(item.filename.casefold().endswith("vbaproject.bin") for item in infos):
                raise LegalDocumentParserError("Macro-enabled Office content is not accepted by this DOCX parser.")
    except BadZipFile as exc:
        raise LegalDocumentParserError("The DOCX container is invalid or corrupted.") from exc


def _pdf_block_font_info(page: fitz.Page) -> dict[int, tuple[float, bool]]:
    info: dict[int, tuple[float, bool]] = {}
    raw = page.get_text("dict")
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        block_no = int(block.get("number", -1))
        sizes: list[float] = []
        bold = False
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text", "")).strip()
                if not text:
                    continue
                sizes.append(float(span.get("size", 0.0)))
                font_name = str(span.get("font", "")).casefold()
                if "bold" in font_name or "black" in font_name or "demi" in font_name:
                    bold = True
        if sizes:
            info[block_no] = (max(sizes), bold)
    return info


def _parse_pdf(data: bytes, filename: str | None, options: ParseOptions) -> ParseResponse:
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise LegalDocumentParserError("The PDF is invalid or corrupted.") from exc

    try:
        if document.needs_pass:
            raise LegalDocumentParserError("Password-protected PDFs are not supported.")
        if document.page_count > MAX_PDF_PAGES:
            raise LegalDocumentParserError(f"PDF exceeds the {MAX_PDF_PAGES:,}-page safety limit.")

        parts: list[str] = []
        pages: list[ParsedPage] = []
        blocks: list[ParsedBlock] = []
        headings: list[ParsedHeading] = []
        warnings: list[str] = []
        pdf_meta = document.metadata or {}
        paragraph_count = 0
        text_length = 0

        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            raw_blocks = [item for item in page.get_text("blocks") if len(item) >= 7 and int(item[6]) == 0]
            raw_blocks.sort(key=lambda item: (round(float(item[1]), 1), round(float(item[0]), 1)))
            font_info = _pdf_block_font_info(page) if options.detect_headings else {}
            font_sizes = [value[0] for value in font_info.values() if value[0] > 0]
            body_font = median(font_sizes) if font_sizes else 0.0

            page_parts: list[str] = []
            if parts:
                parts.append("\n\n")
                text_length += 2
            page_start = text_length

            for raw in raw_blocks:
                text = _clean_block_text(str(raw[4]))
                if not text:
                    continue
                if page_parts:
                    page_parts.append("\n\n")
                    parts.append("\n\n")
                    text_length += 2
                block_start = text_length
                page_parts.append(text)
                parts.append(text)
                block_end = block_start + len(text)
                text_length = block_end
                paragraph_count += 1

                block_no = int(raw[5])
                max_font, bold = font_info.get(block_no, (0.0, False))
                is_heading = False
                level: int | None = None
                if options.detect_headings and body_font > 0 and len(text) <= 180:
                    relative = max_font / body_font if body_font else 1.0
                    is_heading = (relative >= 1.18 or (bold and relative >= 1.05)) and len(text.split()) <= 24
                    if is_heading:
                        if relative >= 1.65:
                            level = 1
                        elif relative >= 1.35:
                            level = 2
                        else:
                            level = 3

                block_type = BlockType.HEADING if is_heading else BlockType.PARAGRAPH
                parsed_block = ParsedBlock(
                    block_index=len(blocks),
                    block_type=block_type,
                    text=text,
                    char_start=block_start,
                    char_end=block_end,
                    page_number=page_index + 1,
                    paragraph_index=paragraph_count,
                    heading_level=level,
                )
                blocks.append(parsed_block)
                if is_heading:
                    headings.append(
                        ParsedHeading(
                            text=text,
                            level=level,
                            method=HeadingMethod.PDF_FONT_HEURISTIC,
                            block_index=parsed_block.block_index,
                            char_start=block_start,
                            char_end=block_end,
                            page_number=page_index + 1,
                        )
                    )

            page_text = "".join(page_parts)
            page_end = page_start + len(page_text)
            pages.append(
                ParsedPage(
                    page_number=page_index + 1,
                    text=page_text,
                    char_start=page_start,
                    char_end=page_end,
                )
            )

        full_text = "".join(parts)
        if len(full_text) > options.max_extracted_chars:
            raise LegalDocumentParserError(
                f"Extracted text exceeds the configured {options.max_extracted_chars:,}-character limit."
            )
        if document.page_count and not full_text.strip():
            warnings.append("No searchable text was extracted. The PDF may be scanned/image-only and require OCR.")
        elif any(not page.text.strip() for page in pages):
            warnings.append("One or more PDF pages contain no searchable text and may require OCR.")
        if headings:
            warnings.append("PDF headings are inferred from font size/style and should be reviewed.")

        metadata = DocumentMetadata(
            original_filename=filename,
            detected_format=DocumentFormat.PDF,
            mime_type="application/pdf",
            file_size_bytes=len(data),
            sha256=_sha256(data),
            title=(pdf_meta.get("title") or None),
            author=(pdf_meta.get("author") or None),
            subject=(pdf_meta.get("subject") or None),
            created_at=_parse_pdf_date(pdf_meta.get("creationDate")),
            modified_at=_parse_pdf_date(pdf_meta.get("modDate")),
            page_count=document.page_count,
            paragraph_count=paragraph_count,
            table_count=0,
            heading_count=len(headings),
            word_count=_word_count(full_text),
            character_count=len(full_text),
        )
        return ParseResponse(
            metadata=metadata,
            text=full_text if options.include_text else None,
            pages=pages if options.include_pages else [],
            blocks=blocks if options.include_blocks else [],
            headings=headings if options.detect_headings else [],
            tables=[],
            warnings=warnings,
            disclaimer=DISCLAIMER,
        )
    finally:
        document.close()


def _iter_docx_body(document: DocxDocument):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield "paragraph", Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield "table", Table(child, document)


def _docx_datetime(value) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _docx_heading_level(paragraph: Paragraph) -> int | None:
    style_name = (paragraph.style.name if paragraph.style else "") or ""
    match = re.match(r"Heading\s+(\d+)$", style_name.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    value = int(match.group(1))
    return max(1, min(value, 9))


def _parse_docx(data: bytes, filename: str | None, options: ParseOptions) -> ParseResponse:
    _validate_docx_archive(data)
    try:
        document = Document(BytesIO(data))
    except Exception as exc:
        raise LegalDocumentParserError("The DOCX is invalid or corrupted.") from exc

    parts: list[str] = []
    blocks: list[ParsedBlock] = []
    headings: list[ParsedHeading] = []
    tables: list[ParsedTable] = []
    warnings = [
        "DOCX page count is not reported because pagination depends on the rendering engine, fonts, and layout environment."
    ]
    paragraph_index = 0
    table_index = 0
    text_length = 0

    for kind, item in _iter_docx_body(document):
        if kind == "paragraph":
            paragraph: Paragraph = item
            text = _clean_block_text(paragraph.text)
            if not text:
                continue
            paragraph_index += 1
            start, end, text_length = _append_piece(parts, text, text_length)
            heading_level = _docx_heading_level(paragraph) if options.detect_headings else None
            block = ParsedBlock(
                block_index=len(blocks),
                block_type=BlockType.HEADING if heading_level is not None else BlockType.PARAGRAPH,
                text=text,
                char_start=start,
                char_end=end,
                paragraph_index=paragraph_index,
                heading_level=heading_level,
            )
            blocks.append(block)
            if heading_level is not None:
                headings.append(
                    ParsedHeading(
                        text=text,
                        level=heading_level,
                        method=HeadingMethod.DOCX_STYLE,
                        block_index=block.block_index,
                        char_start=start,
                        char_end=end,
                    )
                )
        else:
            table: Table = item
            rows: list[list[str]] = []
            for row in table.rows:
                rows.append([_clean_block_text(cell.text) for cell in row.cells])
            if not rows:
                continue
            table_index += 1
            table_text = "\n".join("\t".join(cells) for cells in rows).strip()
            if not table_text:
                continue
            start, end, text_length = _append_piece(parts, table_text, text_length)
            column_count = max((len(row) for row in rows), default=0)
            parsed_table = ParsedTable(
                table_index=table_index,
                rows=rows,
                row_count=len(rows),
                column_count=column_count,
                char_start=start,
                char_end=end,
            )
            tables.append(parsed_table)
            blocks.append(
                ParsedBlock(
                    block_index=len(blocks),
                    block_type=BlockType.TABLE,
                    text=table_text,
                    char_start=start,
                    char_end=end,
                    table_index=table_index,
                )
            )

    full_text = "".join(parts)
    if len(full_text) > options.max_extracted_chars:
        raise LegalDocumentParserError(
            f"Extracted text exceeds the configured {options.max_extracted_chars:,}-character limit."
        )

    props = document.core_properties
    metadata = DocumentMetadata(
        original_filename=filename,
        detected_format=DocumentFormat.DOCX,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size_bytes=len(data),
        sha256=_sha256(data),
        title=props.title or None,
        author=props.author or None,
        subject=props.subject or None,
        created_at=_docx_datetime(props.created),
        modified_at=_docx_datetime(props.modified),
        page_count=None,
        paragraph_count=paragraph_index,
        table_count=len(tables),
        heading_count=len(headings),
        word_count=_word_count(full_text),
        character_count=len(full_text),
    )
    return ParseResponse(
        metadata=metadata,
        text=full_text if options.include_text else None,
        pages=[],
        blocks=blocks if options.include_blocks else [],
        headings=headings if options.detect_headings else [],
        tables=tables if options.include_tables else [],
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )


def parse_legal_document(
    data: bytes,
    options: ParseOptions | None = None,
    *,
    original_filename: str | None = None,
) -> ParseResponse:
    options = options or ParseOptions()
    _validate_size(data)
    detected = _detect_format(data)
    if detected == DocumentFormat.PDF:
        return _parse_pdf(data, original_filename, options)
    if detected == DocumentFormat.DOCX:
        return _parse_docx(data, original_filename, options)
    raise LegalDocumentParserError("Unsupported document format.")


def supported_formats() -> list[dict[str, object]]:
    return [
        {
            "format": "pdf",
            "mime_type": "application/pdf",
            "features": ["searchable text", "page boundaries", "text blocks", "font-based heading hints"],
            "limitations": ["no OCR in this tool", "no PDF table extraction"],
        },
        {
            "format": "docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "features": ["paragraph order", "heading styles", "tables", "core metadata"],
            "limitations": ["no reliable rendered page count"],
        },
    ]
