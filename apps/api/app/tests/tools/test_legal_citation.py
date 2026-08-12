from fastapi.testclient import TestClient

from app.main import app
from app.tools.legal_citation.models import CitationExtractRequest, CitationFormatRequest, CitationKind
from app.tools.legal_citation.service import extract_citations, format_citation

client = TestClient(app)


def test_formats_scc_citation() -> None:
    result = format_citation(
        CitationFormatRequest(kind=CitationKind.SCC, year=2024, volume=5, page_or_number=123)
    )
    assert result.citation == "(2024) 5 SCC 123"


def test_formats_air_with_case_name_and_normalized_court() -> None:
    result = format_citation(
        CitationFormatRequest(
            kind=CitationKind.AIR,
            year=2024,
            court_code="sc",
            page_or_number=100,
            case_name="  Example   Ltd v State  ",
        )
    )
    assert result.citation == "AIR 2024 SC 100"
    assert result.citation_with_case_name == "Example Ltd v State, AIR 2024 SC 100"


def test_scc_requires_volume() -> None:
    response = client.post(
        "/api/v1/tools/legal-citations/format",
        json={"kind": "scc", "year": 2024, "page_or_number": 123},
    )
    assert response.status_code == 422


def test_extracts_multiple_supported_citation_types() -> None:
    text = "Authorities: (2024) 5 SCC 123; AIR 2023 SC 88; and 2022 SCC OnLine Del 456."
    result = extract_citations(CitationExtractRequest(text=text))
    assert result.match_count == 3
    assert [m.kind for m in result.matches] == [CitationKind.SCC, CitationKind.AIR, CitationKind.SCC_ONLINE]
    assert result.matches[2].normalized == "2022 SCC OnLine DEL 456"


def test_extract_returns_offsets_line_and_column() -> None:
    text = "First line\nSee (2024) 5 SCC 123 for discussion."
    result = extract_citations(CitationExtractRequest(text=text))
    match = result.matches[0]
    assert text[match.start:match.end] == match.raw
    assert match.line == 2
    assert match.column == 5


def test_deduplicates_by_normalized_citation() -> None:
    text = "(2024) 5 SCC 123 and again (2024) 5 scc 123."
    result = extract_citations(CitationExtractRequest(text=text, deduplicate=True))
    assert result.match_count == 1
    assert result.unique_count == 1
    assert any("Removed 1" in warning for warning in result.warnings)


def test_can_keep_duplicate_occurrences() -> None:
    text = "AIR 2024 SC 100; AIR 2024 SC 100"
    result = extract_citations(CitationExtractRequest(text=text, deduplicate=False))
    assert result.match_count == 2
    assert result.unique_count == 1


def test_extract_can_filter_kinds() -> None:
    text = "(2024) 5 SCC 123; AIR 2024 SC 100"
    result = extract_citations(
        CitationExtractRequest(text=text, kinds=[CitationKind.AIR])
    )
    assert result.match_count == 1
    assert result.matches[0].kind == CitationKind.AIR


def test_india_neutral_colon_form_normalizes() -> None:
    result = extract_citations(CitationExtractRequest(text="See 2024:DHC:1234."))
    assert result.matches[0].kind == CitationKind.INDIA_NEUTRAL
    assert result.matches[0].normalized == "2024 DHC 1234"


def test_uk_neutral_format_and_extract() -> None:
    formatted = format_citation(
        CitationFormatRequest(
            kind=CitationKind.UK_NEUTRAL,
            year=2024,
            court_code="EWCA",
            division="Civ",
            page_or_number=321,
        )
    )
    assert formatted.citation == "[2024] EWCA Civ 321"
    extracted = extract_citations(CitationExtractRequest(text=formatted.citation))
    assert extracted.matches[0].normalized == "[2024] EWCA Civ 321"


def test_no_match_returns_warning() -> None:
    result = extract_citations(CitationExtractRequest(text="No reported authority is cited here."))
    assert result.match_count == 0
    assert result.warnings


def test_extract_api() -> None:
    response = client.post(
        "/api/v1/tools/legal-citations/extract",
        json={"text": "See (2024) 5 SCC 123 and AIR 2024 SC 100."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["match_count"] == 2
    assert payload["kinds_found"]["scc"] == 1
