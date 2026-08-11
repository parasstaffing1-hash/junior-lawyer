from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models.case_lookup import CaseSourceKind
from app.services.case_lookup.parser import ParsedCaseQuery


@dataclass(frozen=True, slots=True)
class SourceCapability:
    kind: CaseSourceKind
    live_lookup_available: bool
    requires_user_verification: bool
    description: str


class CaseSourceAdapter(Protocol):
    capability: SourceCapability

    async def search(self, parsed: ParsedCaseQuery, *, state: str | None = None, district: str | None = None, court: str | None = None) -> list[dict]:
        ...


class UserAssistedCourtSource:
    def __init__(self, kind: CaseSourceKind, description: str):
        self.capability = SourceCapability(
            kind=kind,
            live_lookup_available=False,
            requires_user_verification=True,
            description=description,
        )

    async def search(self, parsed: ParsedCaseQuery, *, state: str | None = None, district: str | None = None, court: str | None = None) -> list[dict]:
        return []


DISTRICT_COURT_SOURCE = UserAssistedCourtSource(
    CaseSourceKind.DISTRICT_COURT,
    "District-court official lookup adapter boundary. Where the official flow requires CAPTCHA/user interaction, normalized results must be imported after that supported flow.",
)
HIGH_COURT_SOURCE = UserAssistedCourtSource(
    CaseSourceKind.HIGH_COURT,
    "High Court official lookup adapter boundary. Live connectors can be added only where an approved official interface is available.",
)
SUPREME_COURT_SOURCE = UserAssistedCourtSource(
    CaseSourceKind.SUPREME_COURT,
    "Supreme Court official lookup adapter boundary. Normalized official results are accepted without bypassing protected interfaces.",
)
