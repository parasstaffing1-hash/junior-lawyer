from datetime import date

from app.services.procedure.catalog import BUILTIN_PACKS, get_catalog
from app.services.procedure.extractor import extract_directions


def test_extract_english_direction_with_relative_days():
    rows = extract_directions(
        "The respondent is directed to file an affidavit within 7 days.",
        order_date=date(2026, 8, 8),
    )
    assert len(rows) == 1
    assert rows[0].due_date == date(2026, 8, 15)
    assert rows[0].metadata["calculation_is_provisional"] is True


def test_extract_hindi_direction():
    rows = extract_directions(
        "प्रतिवादी को निर्देश दिया जाता है कि उत्तर 10 दिनों के भीतर दाखिल करें।",
        order_date=date(2026, 8, 8),
    )
    assert len(rows) == 1
    assert rows[0].due_date == date(2026, 8, 18)


def test_non_direction_is_not_extracted():
    assert extract_directions("The matter was heard at length and arguments concluded.") == []


def test_builtin_pack_contains_no_statutory_deadline_claims():
    pack = BUILTIN_PACKS["india_litigation_case_management"]
    assert pack["deadline_rules"] == []
    assert pack["verified"] is False
    assert "no statutory limitation" in pack["description"].casefold()


def test_catalog_marks_workflow_pack_as_unverified():
    row = get_catalog()[0]
    assert row["verified"] is False
    assert row["deadline_rule_count"] == 0
