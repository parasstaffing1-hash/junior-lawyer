from app.models.document_entity import EntityType
from app.services.documents.metadata import extract_entities


def by_type(text: str, entity_type: EntityType) -> list[str]:
    return [
        entity.normalized_value or entity.raw_text
        for entity in extract_entities(text)
        if entity.entity_type == entity_type
    ]


def test_extracts_english_legal_metadata() -> None:
    text = """IN THE HIGH COURT OF DELHI AT NEW DELHI
ABC PRIVATE LIMITED v. XYZ LIMITED
CNR DLHC010012342026
CS(COMM) 284/2026
HON'BLE MR. JUSTICE A. SHARMA
Order dated 12 March 2026
Section 138 of the Negotiable Instruments Act, 1881
(2024) 3 SCC 210
"""

    assert by_type(text, EntityType.CNR_NUMBER) == ["DLHC010012342026"]
    assert "CS(COMM) 284/2026" in by_type(text, EntityType.CASE_NUMBER)
    assert "ABC PRIVATE LIMITED v. XYZ LIMITED" in by_type(text, EntityType.CASE_TITLE)
    assert "2026-03-12" in by_type(text, EntityType.DATE)
    assert "section:138" in by_type(text, EntityType.STATUTE_REFERENCE)
    assert "(2024) 3 SCC 210" in by_type(text, EntityType.CITATION)
    assert any("HIGH COURT OF DELHI" in value for value in by_type(text, EntityType.COURT))
    assert any("JUSTICE A. SHARMA" in value for value in by_type(text, EntityType.JUDGE))


def test_extracts_hindi_legal_metadata() -> None:
    text = """माननीय उच्च न्यायालय दिल्ली
राम कुमार बनाम श्याम कुमार
CNR DLHC010012342026
वाद संख्या 123/2026
न्यायमूर्ति आर. शर्मा
आदेश दिनांक १२ मार्च 2026
धारा 420 भारतीय दंड संहिता, 1860
"""

    assert "राम कुमार v. श्याम कुमार" in by_type(text, EntityType.CASE_TITLE)
    assert "वाद संख्या 123/2026" in by_type(text, EntityType.CASE_NUMBER)
    assert "2026-03-12" in by_type(text, EntityType.DATE)
    assert "section:420" in by_type(text, EntityType.STATUTE_REFERENCE)
    assert any("उच्च न्यायालय" in value for value in by_type(text, EntityType.COURT))
    assert any("भारतीय दंड संहिता" in value for value in by_type(text, EntityType.ACT))


def test_extracts_common_indian_citation_formats() -> None:
    text = "Authorities: AIR 2024 SC 123, 2025 SCC OnLine Del 456, 2026 INSC 78, 2026:DHC:912."
    citations = by_type(text, EntityType.CITATION)

    assert "AIR 2024 SC 123" in citations
    assert "2025 SCC ONLINE DEL 456" in citations
    assert "2026 INSC 78" in citations
    assert "2026:DHC:912" in citations


def test_invalid_calendar_date_is_not_emitted() -> None:
    dates = by_type("Order dated 31/02/2026", EntityType.DATE)
    assert dates == []


def test_extracts_roman_hinglish_case_title_and_number() -> None:
    text = "Ram Kumar banam Shyam Kumar\nmukadma sankhya 123/2026\ndhara 420"
    assert "Ram Kumar v. Shyam Kumar" in by_type(text, EntityType.CASE_TITLE)
    assert "MUKADMA SANKHYA 123/2026" in by_type(text, EntityType.CASE_NUMBER)
    assert "section:420" in by_type(text, EntityType.STATUTE_REFERENCE)
