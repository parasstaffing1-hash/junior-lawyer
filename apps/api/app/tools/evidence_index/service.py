import csv
import io
from collections import Counter

from app.tools.evidence_index.models import (
    EvidenceIndexRequest,
    EvidenceIndexResponse,
    EvidenceIndexSummary,
    IndexDocument,
    IndexType,
    NumberingStyle,
    PaginationMode,
    RenderedIndexDocument,
)


DISCLAIMER = (
    "This index is generated deterministically from user-supplied document metadata. "
    "It does not verify authenticity, admissibility, completeness, privilege, filing requirements, "
    "or whether a document should be described as evidence, an exhibit, or an annexure. "
    "Labels and page references should be checked against the final filed or served bundle."
)


class EvidenceIndexError(ValueError):
    pass


_DEFAULT_PREFIXES = {
    IndexType.EVIDENCE: "E",
    IndexType.EXHIBIT: "EX",
    IndexType.ANNEXURE: "ANN",
    IndexType.BUNDLE: "DOC",
}


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_document(document: IndexDocument) -> IndexDocument:
    title = document.title.strip()
    if not title:
        raise EvidenceIndexError("document title cannot be blank")
    return document.model_copy(
        update={
            "title": title,
            "description": _clean_optional(document.description),
            "category": _clean_optional(document.category),
            "label": _clean_optional(document.label),
            "source_file": _clean_optional(document.source_file),
            "notes": _clean_optional(document.notes),
        }
    )


def _alpha_number(number: int) -> str:
    if number < 1:
        raise EvidenceIndexError("alphabetic numbering requires a positive number")
    chars: list[str] = []
    value = number
    while value:
        value, remainder = divmod(value - 1, 26)
        chars.append(chr(ord("A") + remainder))
    return "".join(reversed(chars))


def _generated_label(
    sequence_number: int,
    prefix: str,
    style: NumberingStyle,
    zero_pad: int,
) -> str:
    if style == NumberingStyle.ALPHABETIC:
        token = _alpha_number(sequence_number)
    else:
        token = str(sequence_number).zfill(zero_pad) if zero_pad else str(sequence_number)
    return f"{prefix}-{token}" if prefix else token


def _page_range(start_page: int | None, end_page: int | None) -> str | None:
    if start_page is None or end_page is None:
        return None
    if start_page == end_page:
        return str(start_page)
    return f"{start_page}-{end_page}"


def _validate_provided_pages(documents: list[IndexDocument]) -> list[str]:
    ranges = sorted(
        [(doc.start_page, doc.end_page, index + 1) for index, doc in enumerate(documents)],
        key=lambda item: (item[0], item[1]),
    )
    gaps: list[str] = []
    previous_end: int | None = None
    previous_entry: int | None = None
    for start, end, entry_number in ranges:
        assert start is not None and end is not None
        if previous_end is not None:
            if start <= previous_end:
                raise EvidenceIndexError(
                    f"page range overlap between entries {previous_entry} and {entry_number}"
                )
            if start > previous_end + 1:
                gap_start = previous_end + 1
                gap_end = start - 1
                gaps.append(str(gap_start) if gap_start == gap_end else f"{gap_start}-{gap_end}")
        previous_end = end
        previous_entry = entry_number
    return gaps


def _render_markdown(
    title: str,
    case_reference: str | None,
    documents: list[RenderedIndexDocument],
) -> str:
    lines = [f"# {title}"]
    if case_reference:
        lines.extend(["", f"Case reference: {case_reference}"])
    lines.extend(
        [
            "",
            "| # | Label | Date | Document | Category | Pages | Source |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for doc in documents:
        title_text = doc.title
        if doc.description:
            title_text += f" — {doc.description}"
        title_text = title_text.replace("|", "\\|").replace("\n", " ")
        category = (doc.category or "").replace("|", "\\|")
        source = (doc.source_file or "").replace("|", "\\|")
        date_text = doc.document_date.isoformat() if doc.document_date else ""
        lines.append(
            f"| {doc.sequence} | {doc.label} | {date_text} | {title_text} | "
            f"{category} | {doc.page_range or ''} | {source} |"
        )
    return "\n".join(lines)


def _render_csv(case_reference: str | None, documents: list[RenderedIndexDocument]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "sequence",
            "case_reference",
            "label",
            "document_date",
            "title",
            "description",
            "category",
            "source_file",
            "page_count",
            "start_page",
            "end_page",
            "page_range",
            "confidential",
            "notes",
        ]
    )
    for doc in documents:
        writer.writerow(
            [
                doc.sequence,
                case_reference or "",
                doc.label,
                doc.document_date.isoformat() if doc.document_date else "",
                doc.title,
                doc.description or "",
                doc.category or "",
                doc.source_file or "",
                "" if doc.page_count is None else doc.page_count,
                "" if doc.start_page is None else doc.start_page,
                "" if doc.end_page is None else doc.end_page,
                doc.page_range or "",
                str(doc.confidential).lower(),
                doc.notes or "",
            ]
        )
    return output.getvalue()


def generate_evidence_index(request: EvidenceIndexRequest) -> EvidenceIndexResponse:
    documents = [_normalize_document(document) for document in request.documents]

    title = request.title.strip()
    if not title:
        raise EvidenceIndexError("title cannot be blank")
    case_reference = _clean_optional(request.case_reference)
    prefix = _clean_optional(request.label_prefix)
    if prefix is None:
        prefix = _DEFAULT_PREFIXES[request.index_type]

    provided_gaps: list[str] = []
    if request.pagination_mode == PaginationMode.PROVIDED:
        provided_gaps = _validate_provided_pages(documents)

    rendered: list[RenderedIndexDocument] = []
    seen_labels: dict[str, int] = {}
    next_page = request.first_page

    for index, document in enumerate(documents):
        sequence = index + 1
        numbering_value = request.numbering_start + index
        label = document.label or _generated_label(
            numbering_value,
            prefix,
            request.numbering_style,
            request.zero_pad,
        )
        label_key = label.casefold()
        if label_key in seen_labels:
            raise EvidenceIndexError(
                f"duplicate label '{label}' at entries {seen_labels[label_key]} and {sequence}"
            )
        seen_labels[label_key] = sequence

        start_page: int | None = None
        end_page: int | None = None
        page_count = document.page_count

        if request.pagination_mode == PaginationMode.AUTO:
            assert page_count is not None
            start_page = next_page
            end_page = start_page + page_count - 1
            next_page = end_page + 1
        elif request.pagination_mode == PaginationMode.PROVIDED:
            start_page = document.start_page
            end_page = document.end_page
            assert start_page is not None and end_page is not None
            page_count = end_page - start_page + 1

        rendered.append(
            RenderedIndexDocument(
                sequence=sequence,
                label=label,
                title=document.title,
                document_date=document.document_date,
                description=document.description,
                category=document.category,
                source_file=document.source_file,
                page_count=page_count,
                start_page=start_page,
                end_page=end_page,
                page_range=_page_range(start_page, end_page),
                notes=document.notes,
                confidential=document.confidential,
            )
        )

    warnings: list[str] = []
    duplicate_identity = Counter(
        (doc.title.casefold(), doc.document_date.isoformat() if doc.document_date else "")
        for doc in rendered
    )
    if any(count > 1 for count in duplicate_identity.values()):
        warnings.append("Possible duplicate documents share the same title and document date.")
    if any(doc.document_date is None for doc in rendered):
        warnings.append("One or more documents have no document date.")
    if any(doc.source_file is None for doc in rendered):
        warnings.append("One or more documents have no source file/reference.")
    if provided_gaps:
        warnings.append("Provided pagination contains page gaps; review the missing page ranges.")

    categories = Counter(doc.category for doc in rendered if doc.category)
    if request.pagination_mode == PaginationMode.NONE:
        total_pages = None
        first_page = None
        last_page = None
    else:
        total_pages = sum(doc.page_count or 0 for doc in rendered)
        first_page = min(doc.start_page for doc in rendered if doc.start_page is not None)
        last_page = max(doc.end_page for doc in rendered if doc.end_page is not None)

    summary = EvidenceIndexSummary(
        document_count=len(rendered),
        confidential_count=sum(doc.confidential for doc in rendered),
        dated_document_count=sum(doc.document_date is not None for doc in rendered),
        total_pages=total_pages,
        first_page=first_page,
        last_page=last_page,
        page_gaps=provided_gaps,
        category_counts=dict(sorted(categories.items(), key=lambda item: item[0].casefold())),
    )

    return EvidenceIndexResponse(
        case_reference=case_reference,
        title=title,
        index_type=request.index_type,
        documents=rendered,
        summary=summary,
        markdown=_render_markdown(title, case_reference, rendered),
        csv=_render_csv(case_reference, rendered),
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
