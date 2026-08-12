import csv
import io
from collections import Counter
from datetime import date

from app.tools.case_timeline.models import (
    CaseTimelineRequest,
    CaseTimelineResponse,
    RenderedTimelineEvent,
    TimelineEvent,
    TimelineImportance,
    TimelineSummary,
)


DISCLAIMER = (
    "This chronology is a deterministic organization of user-supplied information. "
    "It does not verify facts, evidence, procedural significance, or legal relevance. "
    "Dates and source references should be checked against the underlying record before use."
)


class CaseTimelineError(ValueError):
    pass


def _clean_list(values: list[str], field_name: str) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            raise CaseTimelineError(f"{field_name} cannot contain blank values")
        key = value.casefold()
        if key not in seen:
            cleaned.append(value)
            seen.add(key)
    return cleaned


def _normalize_event(event: TimelineEvent) -> TimelineEvent:
    title = event.title.strip()
    if not title:
        raise CaseTimelineError("event title cannot be blank")

    description = event.description.strip() if event.description and event.description.strip() else None
    parties = _clean_list(event.parties, "parties")
    tags = _clean_list(event.tags, "tags")

    refs = []
    for index, ref in enumerate(event.source_references, start=1):
        label = ref.label.strip()
        if not label:
            raise CaseTimelineError(f"source reference {index} label cannot be blank")
        refs.append(
            ref.model_copy(
                update={
                    "label": label,
                    "document_id": ref.document_id.strip() if ref.document_id and ref.document_id.strip() else None,
                    "page": ref.page.strip() if ref.page and ref.page.strip() else None,
                    "note": ref.note.strip() if ref.note and ref.note.strip() else None,
                }
            )
        )

    return event.model_copy(
        update={
            "title": title,
            "description": description,
            "parties": parties,
            "tags": tags,
            "source_references": refs,
        }
    )


def _event_dates(event: TimelineEvent) -> tuple[date, date | None, str]:
    if event.event_date is not None:
        return event.event_date, None, event.event_date.isoformat()

    assert event.start_date is not None
    if event.end_date is None or event.end_date == event.start_date:
        return event.start_date, event.end_date, event.start_date.isoformat()
    return event.start_date, event.end_date, f"{event.start_date.isoformat()} to {event.end_date.isoformat()}"


def _sort_key(event: TimelineEvent, original_index: int) -> tuple[date, date, int]:
    start, end, _ = _event_dates(event)
    return start, end or start, original_index


def _format_sources(event: RenderedTimelineEvent) -> str:
    if not event.source_references:
        return ""
    parts: list[str] = []
    for ref in event.source_references:
        text = ref.label
        if ref.document_id:
            text += f" [{ref.document_id}]"
        if ref.page:
            text += f", p. {ref.page}"
        if ref.note:
            text += f" ({ref.note})"
        parts.append(text)
    return "; ".join(parts)


def _render_markdown(title: str, case_reference: str | None, events: list[RenderedTimelineEvent]) -> str:
    lines = [f"# {title}"]
    if case_reference:
        lines.extend(["", f"Case reference: {case_reference}"])
    lines.extend(["", "| # | Date | Type | Importance | Event | Sources |", "|---:|---|---|---|---|---|"])
    for event in events:
        event_text = event.title
        if event.description:
            event_text += f" — {event.description}"
        event_text = event_text.replace("|", "\\|").replace("\n", " ")
        sources = _format_sources(event).replace("|", "\\|")
        lines.append(
            f"| {event.sequence} | {event.display_date} | {event.event_type.value} | "
            f"{event.importance.value} | {event_text} | {sources} |"
        )
    return "\n".join(lines)


def _render_csv(case_reference: str | None, events: list[RenderedTimelineEvent]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "sequence",
            "case_reference",
            "date",
            "start_date",
            "end_date",
            "event_type",
            "importance",
            "title",
            "description",
            "parties",
            "tags",
            "sources",
            "days_since_previous",
        ]
    )
    for event in events:
        writer.writerow(
            [
                event.sequence,
                case_reference or "",
                event.display_date,
                event.start_date.isoformat(),
                event.end_date.isoformat() if event.end_date else "",
                event.event_type.value,
                event.importance.value,
                event.title,
                event.description or "",
                "; ".join(event.parties),
                "; ".join(event.tags),
                _format_sources(event),
                "" if event.days_since_previous is None else event.days_since_previous,
            ]
        )
    return output.getvalue()


def generate_case_timeline(request: CaseTimelineRequest) -> CaseTimelineResponse:
    normalized_events = [_normalize_event(event) for event in request.events]
    indexed = list(enumerate(normalized_events))
    indexed.sort(key=lambda item: _sort_key(item[1], item[0]))

    rendered: list[RenderedTimelineEvent] = []
    previous_start: date | None = None
    for sequence, (_, event) in enumerate(indexed, start=1):
        start, end, display = _event_dates(event)
        gap = None
        if request.include_day_gaps and previous_start is not None:
            gap = (start - previous_start).days
        rendered.append(
            RenderedTimelineEvent(
                sequence=sequence,
                sort_date=start,
                display_date=display,
                start_date=start,
                end_date=end,
                title=event.title,
                description=event.description,
                event_type=event.event_type,
                importance=event.importance,
                parties=event.parties,
                source_references=event.source_references,
                tags=event.tags,
                days_since_previous=gap,
            )
        )
        previous_start = start

    first_date = rendered[0].start_date
    last_date = max((event.end_date or event.start_date) for event in rendered)
    counts = Counter(event.importance for event in rendered)
    summary = TimelineSummary(
        event_count=len(rendered),
        first_date=first_date,
        last_date=last_date,
        span_days=(last_date - first_date).days,
        critical_count=counts[TimelineImportance.CRITICAL],
        high_count=counts[TimelineImportance.HIGH],
        events_with_sources=sum(bool(event.source_references) for event in rendered),
    )

    warnings: list[str] = []
    if any(not event.source_references for event in rendered):
        warnings.append("One or more events have no source reference.")
    duplicate_dates = Counter(event.start_date for event in rendered)
    if any(count > 1 for count in duplicate_dates.values()):
        warnings.append("Multiple events share the same start date; their original input order was preserved.")

    title = request.title.strip()
    case_reference = request.case_reference.strip() if request.case_reference and request.case_reference.strip() else None
    return CaseTimelineResponse(
        case_reference=case_reference,
        title=title,
        events=rendered,
        summary=summary,
        markdown=_render_markdown(title, case_reference, rendered),
        csv=_render_csv(case_reference, rendered),
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
