from app.services.crm.conflicts import CandidateInput, name_match_score, normalize_party_name, score_candidate


def test_normalize_english_honorifics():
    assert normalize_party_name("Mr. Rajesh Kumar") == "rajesh kumar"


def test_normalize_hindi_honorifics():
    assert normalize_party_name("श्री राम कुमार") == "राम कुमार"


def test_name_token_order_match():
    assert name_match_score("Kumar Rajesh", "Rajesh Kumar") > 0.95


def test_exact_email_is_strong_conflict_signal():
    hit = score_candidate(
        "A completely different display name", [], email="client@example.com", phone=None,
        candidate=CandidateInput("client", None, "Other Name", email="CLIENT@example.com"),
    )
    assert hit is not None
    assert hit[0] == 1.0
    assert "exact email" in hit[1]


def test_phone_normalizes_india_prefix():
    hit = score_candidate(
        "Someone", [], email=None, phone="+91 98765 43210",
        candidate=CandidateInput("contact", None, "Someone Else", phone="9876543210"),
    )
    assert hit is not None
    assert hit[0] == 1.0


def test_weak_name_is_not_candidate():
    hit = score_candidate(
        "Rakesh Sharma", [], email=None, phone=None,
        candidate=CandidateInput("client", None, "Amit Verma"),
    )
    assert hit is None


def test_related_party_can_trigger_candidate():
    hit = score_candidate(
        "ABC Private Limited", ["Shyam Kumar"], email=None, phone=None,
        candidate=CandidateInput("matter", None, "Shyam Kumar v State"),
    )
    assert hit is not None


def test_restricted_candidate_hides_reason_detail():
    hit = score_candidate(
        "Acme India", [], email=None, phone=None,
        candidate=CandidateInput("matter", None, "Acme India", restricted=True),
    )
    assert hit is not None
    assert hit[1] == "possible match in restricted matter"
