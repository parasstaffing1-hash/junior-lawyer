from types import SimpleNamespace

from app.models.ai import AIClaimStatus
from app.services.ai.verification import audit_claims


def sources():
    return [
        SimpleNamespace(source_key="S1", text="The agreement was executed on 12 March 2026 by ABC and XYZ."),
        SimpleNamespace(source_key="S2", text="The respondent denied receiving payment under the agreement."),
    ]


def test_supported_claim_with_known_source():
    audits = audit_claims("The agreement was executed on 12 March 2026. [S1]", sources())
    assert audits[0].status == AIClaimStatus.SUPPORTED


def test_uncited_substantive_claim_is_flagged():
    audits = audit_claims("The agreement was executed on 12 March 2026.", sources())
    assert audits[0].status == AIClaimStatus.UNCITED


def test_invented_source_key_is_hard_flag():
    audits = audit_claims("The agreement was executed on 12 March 2026. [S99]", sources())
    assert audits[0].status == AIClaimStatus.INVALID_SOURCE


def test_low_overlap_source_is_flagged_for_review():
    audits = audit_claims("The Supreme Court conclusively prohibited every form of termination. [S2]", sources())
    assert audits[0].status == AIClaimStatus.WEAK_SUPPORT


def test_insufficiency_statement_does_not_require_citation():
    audits = audit_claims("Not established from the provided sources.", sources())
    assert audits[0].status == AIClaimStatus.NON_SUBSTANTIVE


def test_two_sentences_keep_their_own_trailing_source_markers():
    audits = audit_claims(
        "The agreement was executed on 12 March 2026. [S1] The respondent denied receiving payment. [S2]",
        sources(),
    )
    assert len(audits) == 2
    assert audits[0].cited_source_keys == ["S1"]
    assert audits[1].cited_source_keys == ["S2"]
