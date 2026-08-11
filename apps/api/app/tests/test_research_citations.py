from app.services.research.citations import parse_citations


def test_parses_indian_reported_and_neutral_citations() -> None:
    text = (
        "See (2024) 5 SCC 123, 2024 SCC OnLine SC 456, AIR 2024 SC 789, "
        "2024 INSC 321 and 2024:DHC:999."
    )
    citations = parse_citations(text)
    assert [item.reporter for item in citations] == [
        "SCC", "SCC_ONLINE", "AIR", "INSC", "NEUTRAL"
    ]
    assert citations[0].year == 2024
    assert citations[0].volume == 5
    assert citations[0].page_or_number == 123
    assert citations[-1].court == "DHC"


def test_citation_normalization_is_stable() -> None:
    item = parse_citations("  (2023)   2 SCC  40  ")[0]
    assert item.normalized == "(2023) 2 SCC 40"


def test_unrecognized_text_produces_no_citations() -> None:
    assert parse_citations("no legal citation here") == []
