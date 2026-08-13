"""The drafting library: structure, integrity, and its verification status.

These are contract tests over legal content. They cannot tell whether a
template is legally correct — only a practitioner can — but they can hold the
shape steady so 93 entries stay usable as one catalogue.
"""

import pytest

from app.models.drafting import LegalDraftType
from app.services.drafting import library


def test_the_library_is_substantial_and_covers_every_category():
    templates = library.list_templates()
    assert len(templates) >= 90
    covered = {entry["category"] for entry in templates}
    assert covered == set(library.CATEGORIES)


def test_the_tehsil_practice_essentials_are_present():
    # The instruments a district and revenue practice files most often. If any
    # of these disappears, the library has lost its purpose.
    essentials = {
        "notice-cheque-dishonour-138",
        "crim-bail-regular",
        "crim-bail-anticipatory",
        "crim-complaint-138",
        "app-restoration-dismissal",
        "app-condonation-delay",
        "app-temporary-injunction",
        "plaint-recovery-money",
        "plaint-permanent-injunction",
        "written-statement-civil",
        "revenue-mutation",
        "revenue-partition-agricultural",
        "family-maintenance",
        "family-divorce-mutual",
        "mact-claim-petition",
        "vakalatnama",
        "affidavit-general",
        "deed-sale",
        "deed-will",
    }
    assert essentials <= set(library.TEMPLATES)


def test_every_code_is_unique():
    codes = [entry["code"] for entry in library.list_templates()]
    assert len(codes) == len(set(codes))


@pytest.mark.parametrize("code", sorted(library.TEMPLATES))
def test_each_template_is_well_formed(code):
    entry = library.TEMPLATES[code]
    # Maps onto a category the deterministic builder already understands, so
    # the library never requires a schema change to grow.
    assert isinstance(entry["draft_type"], LegalDraftType)
    assert entry["category"] in library.CATEGORIES
    assert entry["sections"], "a draft with no sections renders as an empty document"
    assert entry["questions"]

    # Bilingual throughout: a Hindi-only practice must not meet English-only
    # labels halfway through a form.
    assert entry["name_en"].strip() and entry["name_hi"].strip()
    for section in entry["sections"]:
        assert section["title_en"].strip() and section["title_hi"].strip()
    for question in entry["questions"]:
        assert question["label_en"].strip() and question["label_hi"].strip()
        assert question["kind"] in {"text", "textarea", "number", "date", "select"}

    # Section and question keys must be unique inside one template, or answers
    # and rendered sections collide.
    section_keys = [s["key"] for s in entry["sections"]]
    question_keys = [q["key"] for q in entry["questions"]]
    assert len(section_keys) == len(set(section_keys))
    assert len(question_keys) == len(set(question_keys))


@pytest.mark.parametrize("code", sorted(library.TEMPLATES))
def test_no_template_claims_to_be_verified(code):
    # The whole library ships unverified. A template becomes verified only when
    # an advocate signs it off for a named jurisdiction — the same rule the
    # remedy rule packs enforce. This test is the tripwire against that slipping.
    assert library.TEMPLATES[code]["verified"] is False


def test_court_filings_carry_their_statutory_basis():
    # Deeds and certificates vary too much by state to name one provision, but
    # a pleading or application without its authority cannot be checked by the
    # advocate reviewing it.
    for entry in library.list_templates():
        if entry["category"] in {"civil-pleadings", "criminal", "family", "appeals"}:
            assert entry["authority"], f"{entry['code']} has no statutory basis recorded"


# --- filtering ----------------------------------------------------------------


def test_filtering_by_category():
    revenue = library.list_templates(category="revenue")
    assert revenue
    assert {entry["category"] for entry in revenue} == {"revenue"}


def test_filtering_by_forum():
    revenue_court = library.list_templates(forum="revenue-court")
    assert revenue_court
    assert all(entry["forum"] == "revenue-court" for entry in revenue_court)


def test_search_matches_english_hindi_and_code():
    assert any(e["code"] == "notice-cheque-dishonour-138" for e in library.list_templates(search="cheque"))
    assert library.list_templates(search="नामांतरण")
    assert library.list_templates(search="revenue-mutation")


def test_search_is_case_insensitive_and_trims():
    assert library.list_templates(search="  BAIL  ")


def test_an_unmatched_search_returns_nothing_rather_than_everything():
    assert library.list_templates(search="zzzz-no-such-draft") == []


def test_get_template_returns_none_for_an_unknown_code():
    assert library.get_template("no-such-code") is None
    assert library.get_template("vakalatnama") is not None
