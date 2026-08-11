from __future__ import annotations

from dataclasses import dataclass

from app.models.operations import CourtSourceKind


@dataclass(frozen=True, slots=True)
class CourtSourceCapability:
    source_kind: CourtSourceKind
    automatic_fetch: bool
    requires_user_or_approved_connector: bool
    note: str


def source_capabilities() -> list[CourtSourceCapability]:
    return [
        CourtSourceCapability(CourtSourceKind.MANUAL, False, False, "Manual court-status snapshot entered by the legal team."),
        CourtSourceCapability(CourtSourceKind.ECOURTS_MANUAL, False, True, "Official eCourts data may be recorded/imported; no CAPTCHA bypass is implemented."),
        CourtSourceCapability(CourtSourceKind.OFFICIAL_IMPORT, False, True, "Import from an approved official export or connector."),
        CourtSourceCapability(CourtSourceKind.MOCK, True, False, "Local development/test source only."),
    ]
