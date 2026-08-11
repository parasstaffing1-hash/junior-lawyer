from app.services.knowledge.ranking import build_search_text, content_hash, rank_knowledge


def test_content_hash_is_stable_under_whitespace():
    a = content_hash(title="Termination clause", body_en="Either party may terminate.", body_hi=None, summary="Approved clause")
    b = content_hash(title="  Termination   clause ", body_en="Either   party may terminate.\n", body_hi=None, summary="Approved   clause")
    assert a == b
    assert len(a) == 64


def test_bilingual_search_normalization_finds_cross_language_concept():
    docs = [
        build_search_text(title="Bail note", body_en="Principles governing bail and evidence.", body_hi=None, summary=None),
        build_search_text(title="जमानत नोट", body_en=None, body_hi="जमानत और साक्ष्य पर स्वीकृत नोट।", summary=None),
        build_search_text(title="Arbitration", body_en="Arbitration seat and appointment.", body_hi=None, summary=None),
    ]
    normalized, ranked = rank_knowledge("zamanat evidence", docs, [0.8, 0.9, 0.9])
    assert normalized
    assert ranked
    assert {ranked[0].index, ranked[1].index} == {0, 1}
    assert all(item.final_score > 0 for item in ranked[:2])


def test_quality_is_only_tiebreaker_not_magic_match():
    docs = ["limitation notice service", "completely unrelated corporate tax text"]
    _, ranked = rank_knowledge("notice service", docs, [0.2, 1.0])
    assert ranked[0].index == 0
    assert all(item.index != 1 for item in ranked)
