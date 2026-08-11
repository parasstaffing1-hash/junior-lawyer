from decimal import Decimal

import pytest

from app.models.client_money import ClientMoneyLedgerAccount, JournalEntryType
from app.services.client_money.ledger import assert_balanced, content_hash, independent_approval_allowed, money, posting_lines, reverse_lines
from app.services.client_money.providers import ManualProvider, MockProvider


def test_deposit_is_balanced_double_entry():
    lines = posting_lines(JournalEntryType.DEPOSIT, Decimal("1000"))
    assert lines[0].account == ClientMoneyLedgerAccount.BANK_CONTROL
    assert lines[0].debit == Decimal("1000.00")
    assert lines[1].account == ClientMoneyLedgerAccount.CLIENT_LIABILITY
    assert lines[1].credit == Decimal("1000.00")
    assert_balanced(lines)


def test_fee_transfer_reduces_client_liability_and_bank():
    lines = posting_lines(JournalEntryType.FEE_TRANSFER, Decimal("250.125"))
    assert lines[0].account == ClientMoneyLedgerAccount.CLIENT_LIABILITY
    assert lines[0].debit == Decimal("250.13")
    assert lines[1].account == ClientMoneyLedgerAccount.BANK_CONTROL
    assert lines[1].credit == Decimal("250.13")
    assert_balanced(lines)


def test_refund_is_balanced():
    assert_balanced(posting_lines(JournalEntryType.REFUND, Decimal("99.99")))


def test_nonpositive_posting_rejected():
    with pytest.raises(ValueError):
        posting_lines(JournalEntryType.DEPOSIT, Decimal("0"))


def test_reversal_swaps_debits_and_credits():
    original = posting_lines(JournalEntryType.DEPOSIT, Decimal("40"))
    reversed_lines = reverse_lines(original)
    assert reversed_lines[0].credit == Decimal("40.00")
    assert reversed_lines[1].debit == Decimal("40.00")
    assert_balanced(reversed_lines)


def test_money_is_deterministic_decimal_rounding():
    assert money("10.005") == Decimal("10.01")


def test_content_hash_is_stable():
    a = content_hash({"b": 2, "a": 1})
    b = content_hash({"a": 1, "b": 2})
    assert a == b and len(a) == 64


def test_manual_provider_does_not_create_external_checkout():
    result = ManualProvider().create_intent("abc")
    assert result.checkout_url is None
    assert result.provider_reference == "manual-abc"


def test_mock_provider_is_explicitly_nonproduction():
    result = MockProvider().create_intent("abc")
    assert result.checkout_url and result.checkout_url.startswith("https://example.invalid/")
    assert result.provider_reference and result.provider_reference.startswith("mock-")


def test_separate_approver_control():
    assert independent_approval_allowed("requester", "reviewer", True)
    assert not independent_approval_allowed("same", "same", True)
    assert independent_approval_allowed("same", "same", False)
