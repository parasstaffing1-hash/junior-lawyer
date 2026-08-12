from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.tools.case_timeline.models import (
    CaseTimelineRequest,
    TimelineEvent,
    TimelineImportance,
    TimelineSourceReference,
)
from app.tools.case_timeline.service import generate_case_timeline

client = TestClient(app)


def test_timeline_sorts_events_chronologically() -> None:
    result = generate_case_timeline(
        CaseTimelineRequest(
            case_reference="ABC/2026",
            events=[
                TimelineEvent(event_date=date(2026, 8, 5), title="Notice received"),
                TimelineEvent(event_date=date(2026, 7, 1), title="Agreement signed"),
                TimelineEvent(event_date=date(2026, 7, 20), title="Payment due"),
            ],
        )
    )

    assert [event.title for event in result.events] == [
        "Agreement signed",
        "Payment due",
        "Notice received",
    ]
    assert [event.sequence for event in result.events] == [1, 2, 3]


def test_same_date_preserves_input_order() -> None:
    result = generate_case_timeline(
        CaseTimelineRequest(
            events=[
                TimelineEvent(event_date=date(2026, 7, 1), title="First entered"),
                TimelineEvent(event_date=date(2026, 7, 1), title="Second entered"),
            ]
        )
    )
    assert [event.title for event in result.events] == ["First entered", "Second entered"]
    assert any("same start date" in warning for warning in result.warnings)


def test_date_range_and_summary_use_range_end() -> None:
    result = generate_case_timeline(
        CaseTimelineRequest(
            events=[
                TimelineEvent(start_date=date(2026, 7, 1), end_date=date(2026, 7, 10), title="Negotiations"),
                TimelineEvent(event_date=date(2026, 7, 20), title="Agreement"),
            ]
        )
    )
    assert result.events[0].display_date == "2026-07-01 to 2026-07-10"
    assert result.summary.first_date == date(2026, 7, 1)
    assert result.summary.last_date == date(2026, 7, 20)
    assert result.summary.span_days == 19


def test_day_gaps_are_calculated_from_previous_start_date() -> None:
    result = generate_case_timeline(
        CaseTimelineRequest(
            events=[
                TimelineEvent(event_date=date(2026, 7, 1), title="A"),
                TimelineEvent(event_date=date(2026, 7, 11), title="B"),
            ]
        )
    )
    assert result.events[0].days_since_previous is None
    assert result.events[1].days_since_previous == 10


def test_sources_and_importance_are_summarized() -> None:
    result = generate_case_timeline(
        CaseTimelineRequest(
            events=[
                TimelineEvent(
                    event_date=date(2026, 7, 1),
                    title="Order",
                    importance=TimelineImportance.CRITICAL,
                    source_references=[TimelineSourceReference(label="Court order", page="12")],
                ),
                TimelineEvent(
                    event_date=date(2026, 7, 2),
                    title="Email",
                    importance=TimelineImportance.HIGH,
                ),
            ]
        )
    )
    assert result.summary.critical_count == 1
    assert result.summary.high_count == 1
    assert result.summary.events_with_sources == 1
    assert "Court order, p. 12" in result.markdown
    assert any("no source reference" in warning for warning in result.warnings)


def test_duplicate_parties_and_tags_are_deduplicated_case_insensitively() -> None:
    result = generate_case_timeline(
        CaseTimelineRequest(
            events=[
                TimelineEvent(
                    event_date=date(2026, 7, 1),
                    title="Meeting",
                    parties=["Acme Ltd", "acme ltd", "Client"],
                    tags=["Contract", "contract", "Urgent"],
                )
            ]
        )
    )
    assert result.events[0].parties == ["Acme Ltd", "Client"]
    assert result.events[0].tags == ["Contract", "Urgent"]


def test_csv_is_export_ready() -> None:
    result = generate_case_timeline(
        CaseTimelineRequest(
            case_reference="CASE-1",
            events=[TimelineEvent(event_date=date(2026, 7, 1), title="Agreement, signed")],
        )
    )
    assert result.csv.startswith("sequence,case_reference,date")
    assert '"Agreement, signed"' in result.csv
    assert "CASE-1" in result.csv


def test_invalid_date_combinations_return_422() -> None:
    response = client.post(
        "/api/v1/tools/case-timelines/generate",
        json={
            "events": [
                {
                    "event_date": "2026-07-01",
                    "start_date": "2026-07-01",
                    "title": "Invalid",
                }
            ]
        },
    )
    assert response.status_code == 422


def test_api_generates_timeline() -> None:
    response = client.post(
        "/api/v1/tools/case-timelines/generate",
        json={
            "case_reference": "ABC/2026",
            "title": "Chronology",
            "events": [
                {
                    "event_date": "2026-08-01",
                    "title": "Notice sent",
                    "event_type": "notice",
                    "importance": "high",
                    "source_references": [{"label": "Notice PDF", "document_id": "DOC-7", "page": "1"}],
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["events"][0]["event_type"] == "notice"
    assert payload["summary"]["event_count"] == 1
    assert "# Chronology" in payload["markdown"]
