from uuid import uuid4

from app.models.search import SearchEntityType
from app.services.search.ranking import SearchCandidate, rank_candidates
from app.services.search.service import list_commands


def candidate(kind, title, text=""):
    return SearchCandidate(kind, uuid4(), title, None, text, "/x", [], None, None, {})


def test_exact_matter_title_beats_weak_document_match():
    rows = [
        candidate(SearchEntityType.DOCUMENT, "Payment receipt", "ABC Industries is mentioned once"),
        candidate(SearchEntityType.MATTER, "ABC Industries", "Commercial dispute"),
    ]
    _, _, ranked = rank_candidates("ABC Industries", rows)
    assert ranked[0].candidate.entity_type == SearchEntityType.MATTER


def test_hindi_query_matches_english_legal_concept():
    rows = [
        candidate(SearchEntityType.JUDGMENT, "Bail decision", "anticipatory bail and evidence"),
        candidate(SearchEntityType.DOCUMENT, "Invoice", "professional fee invoice"),
    ]
    normalized, terms, ranked = rank_candidates("जमानत साक्ष्य", rows)
    assert "bail" in terms
    assert ranked[0].candidate.entity_type == SearchEntityType.JUDGMENT
    assert normalized


def test_hinglish_section_search_normalizes():
    rows = [candidate(SearchEntityType.STATUTE, "Negotiable Instruments Act · Section 138", "dishonour of cheque notice")]
    normalized, terms, ranked = rank_candidates("dhara 138 cheque notice", rows)
    assert normalized.startswith("section 138")
    assert ranked and ranked[0].score > 0


def test_command_search_is_bilingual():
    commands = list_commands("साक्ष्य")
    assert any(item["id"] == "go-evidence" for item in commands)
    commands = list_commands("contract")
    assert any(item["id"] == "new-contract" for item in commands)
