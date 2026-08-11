from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.models.client_money import ClientMoneyLedgerAccount, JournalEntryType

TWOPLACES = Decimal("0.01")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class PostingLine:
    account: ClientMoneyLedgerAccount
    debit: Decimal
    credit: Decimal


def posting_lines(entry_type: JournalEntryType, amount: Decimal) -> list[PostingLine]:
    amount = money(amount)
    if amount <= 0:
        raise ValueError("Journal amount must be positive")
    if entry_type == JournalEntryType.DEPOSIT:
        return [
            PostingLine(ClientMoneyLedgerAccount.BANK_CONTROL, amount, money(0)),
            PostingLine(ClientMoneyLedgerAccount.CLIENT_LIABILITY, money(0), amount),
        ]
    if entry_type in {JournalEntryType.REFUND, JournalEntryType.DISBURSEMENT, JournalEntryType.FEE_TRANSFER}:
        return [
            PostingLine(ClientMoneyLedgerAccount.CLIENT_LIABILITY, amount, money(0)),
            PostingLine(ClientMoneyLedgerAccount.BANK_CONTROL, money(0), amount),
        ]
    raise ValueError(f"Use explicit posting lines for {entry_type.value}")


def reverse_lines(lines: list[PostingLine]) -> list[PostingLine]:
    return [PostingLine(line.account, line.credit, line.debit) for line in lines]


def assert_balanced(lines: list[PostingLine]) -> None:
    debit = money(sum((line.debit for line in lines), Decimal("0")))
    credit = money(sum((line.credit for line in lines), Decimal("0")))
    if debit != credit:
        raise ValueError(f"Unbalanced client-money journal: debit={debit} credit={credit}")
    if any(line.debit < 0 or line.credit < 0 for line in lines):
        raise ValueError("Journal lines cannot be negative")


def content_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def independent_approval_allowed(requested_by, approving_user, require_separate_approver: bool = True) -> bool:
    if not require_separate_approver:
        return True
    return requested_by != approving_user
