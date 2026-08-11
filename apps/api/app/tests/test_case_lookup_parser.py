from app.services.case_lookup.parser import normalize_cnr, parse_case_query, rank_case_record


def test_exact_cnr_detection():
    parsed = parse_case_query("UPLU010012342024")
    assert parsed.kind == "cnr"
    assert parsed.cnr == "UPLU010012342024"
    assert normalize_cnr("uplu-010012342024") == "UPLU010012342024"


def test_case_type_number_year_detection():
    parsed = parse_case_query("CS 234/2025")
    assert parsed.kind == "case_number"
    assert parsed.case_type == "CS"
    assert parsed.case_number == "234"
    assert parsed.year == 2025


def test_bare_case_number_year_remains_ambiguous():
    parsed = parse_case_query("234/2025")
    assert parsed.case_type is None
    assert parsed.case_number == "234"
    assert parsed.year == 2025


def test_location_preferences_rank_without_filtering():
    parsed = parse_case_query("CS 234/2025")
    lucknow = {"case_type":"CS","case_number":"234","year":2025,"district":"Lucknow","state":"Uttar Pradesh","court_name":"District Court Lucknow"}
    kanpur = {"case_type":"CS","case_number":"234","year":2025,"district":"Kanpur","state":"Uttar Pradesh","court_name":"District Court Kanpur"}
    assert rank_case_record(lucknow, parsed, district="Lucknow") > rank_case_record(kanpur, parsed, district="Lucknow")


def test_hindi_case_type_is_parsed_without_guessing_abbreviation():
    parsed = parse_case_query("सिविल वाद 234/2025")
    assert parsed.kind == "case_number"
    assert parsed.case_type == "सिविल वाद"
    assert parsed.case_number == "234"
    assert parsed.year == 2025
