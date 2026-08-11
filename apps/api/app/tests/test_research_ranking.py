from app.models.legal_corpus import CourtLevel
from app.services.research.ranking import (
    authority_score,
    bm25_scores,
    expand_query,
    make_snippet,
    tokenize,
)


def test_bilingual_query_expansion() -> None:
    normalized, terms = expand_query("धारा 138 cheque bounce जमानत")
    assert "section" in normalized
    assert "138" in terms
    assert "cheque" in terms
    assert "bail" in terms


def test_hinglish_query_expansion() -> None:
    normalized, terms = expand_query("dhara 138 me zamanat")
    assert "section" in normalized
    assert "138" in terms
    assert "bail" in terms


def test_bm25_ranks_relevant_text_first() -> None:
    _, terms = expand_query("anticipatory bail")
    documents = [
        "The application concerns anticipatory bail and arrest.",
        "This agreement contains an arbitration clause.",
        "Bail may be considered subject to statutory conditions.",
    ]
    scores = bm25_scores(terms, documents)
    assert scores[0] > scores[1]
    assert scores[2] > scores[1]


def test_authority_hierarchy() -> None:
    assert authority_score(CourtLevel.SUPREME_COURT) > authority_score(CourtLevel.HIGH_COURT)
    assert authority_score(CourtLevel.HIGH_COURT) > authority_score(CourtLevel.DISTRICT_COURT)
    assert authority_score(CourtLevel.SUPREME_COURT, bench_strength=5) >= authority_score(CourtLevel.SUPREME_COURT)


def test_make_snippet_centres_match() -> None:
    text = "prefix " * 100 + "important bail principle" + " suffix" * 100
    snippet = make_snippet(text, ["bail"], radius=60)
    assert "bail" in snippet
    assert len(snippet) < len(text)


def test_tokenizer_keeps_devanagari_and_numbers() -> None:
    tokens = tokenize("धारा 138 के तहत जमानत")
    assert "138" in tokens
    assert "section" in tokens
