from app.services.search_index.engine import (
    chunk_text, content_hash, cosine_similarity, duplicate_score, feature_vector,
    hamming_distance, shingle_jaccard, simhash64, simhash_bands,
)


def test_content_hash_is_stable_and_whitespace_normalized():
    assert content_hash("Section 138   notice") == content_hash("Section 138 notice")


def test_simhash_is_stable_hex64():
    value = simhash64("payment receipt bank statement")
    assert len(value) == 16
    assert value == simhash64("payment receipt bank statement")


def test_exact_duplicate_detection():
    score = duplicate_score("The agreement was signed on 12 March.", "The   agreement was signed on 12 March.")
    assert score.exact is True
    assert score.similarity == 1.0


def test_near_duplicate_detection_uses_simhash_and_shingles():
    left = "payment receipt bank statement shows payment of rupees five lakh on 12 march 2026"
    right = "payment receipt bank statement shows payment of rupees five lakh on 12 march 2026 confirmed"
    score = duplicate_score(left, right, max_hamming=20, min_jaccard=0.55)
    assert score.near is True
    assert score.jaccard >= 0.55


def test_different_documents_are_not_near_duplicates():
    score = duplicate_score("employment termination notice probation", "property title possession mutation registry")
    assert score.exact is False
    assert score.near is False


def test_feature_vectors_are_local_deterministic_and_normalized():
    a = feature_vector("धारा 138 cheque notice")
    b = feature_vector("section 138 cheque notice")
    assert len(a) == 128
    assert a == feature_vector("धारा 138 cheque notice")
    assert cosine_similarity(a, b) > 0.30


def test_cosine_similarity_self_is_one():
    v = feature_vector("anticipatory bail evidence")
    assert cosine_similarity(v, v) > 0.999


def test_chunker_overlaps_large_text_without_losing_content_shape():
    text = "\n".join(f"Paragraph {i}. " + ("legal evidence " * 40) for i in range(30))
    chunks = chunk_text(text, max_chars=700, overlap=80)
    assert len(chunks) > 3
    assert all(len(chunk) <= 710 for chunk in chunks)
    assert "Paragraph 0" in chunks[0]


def test_hamming_distance_zero_for_same_simhash():
    value = simhash64("same text here")
    assert hamming_distance(value, value) == 0


def test_shingle_jaccard_is_one_for_identical_text():
    assert shingle_jaccard("a legal notice was served", "a legal notice was served") == 1.0


def test_simhash_bands_are_stable_four_way_lsh_keys():
    value = simhash64("large litigation bundle duplicate page")
    bands = simhash_bands(value)
    assert len(bands) == 4
    assert bands == simhash_bands(value)
    assert all(":" in band for band in bands)


def test_index_feature_vector_can_skip_query_expansion(monkeypatch):
    from app.services.search_index import engine
    def fail(_text):
        raise AssertionError("query expansion should not run while indexing document chunks")
    monkeypatch.setattr(engine, "expand_query", fail)
    vector = engine.feature_vector("Agreement payment evidence धारा 138", expand_legal=False)
    assert len(vector) == 128
    assert any(vector)
