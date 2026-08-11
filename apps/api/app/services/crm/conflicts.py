from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

HONORIFICS = {
    "mr", "mrs", "ms", "miss", "shri", "smt", "dr", "adv", "advocate",
    "श्री", "श्रीमती", "सुश्री", "अधिवक्ता",
}


def normalize_party_name(value: str | None) -> str:
    if not value:
        return ""
    text = value.casefold().strip()
    text = re.sub(r"[^\w\u0900-\u097f]+", " ", text, flags=re.UNICODE)
    tokens = [token for token in text.split() if token and token not in HONORIFICS]
    return " ".join(tokens)


def normalize_email(value: str | None) -> str:
    return (value or "").strip().casefold()


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) > 10:
        digits = digits[-10:]
    return digits


def name_match_score(query: str | None, candidate: str | None) -> float:
    left = normalize_party_name(query)
    right = normalize_party_name(candidate)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    direct = SequenceMatcher(None, left, right).ratio()
    token = SequenceMatcher(None, " ".join(sorted(left.split())), " ".join(sorted(right.split()))).ratio()
    if left in right or right in left:
        direct = max(direct, min(len(left), len(right)) / max(len(left), len(right)))
    left_tokens, right_tokens = set(left.split()), set(right.split())
    if left_tokens and (left_tokens <= right_tokens or right_tokens <= left_tokens):
        # A party name frequently appears inside a longer case title, e.g.
        # "Shyam Kumar" vs "Shyam Kumar v State". Token containment is a strong
        # review signal, but still not an automatic conflict decision.
        direct = max(direct, 0.93)
    return round(max(direct, token), 4)


@dataclass(slots=True)
class CandidateInput:
    candidate_type: str
    candidate_id: object | None
    name: str
    email: str | None = None
    phone: str | None = None
    restricted: bool = False
    metadata: dict | None = None


def score_candidate(subject_name: str, related_parties: list[str], *, email: str | None, phone: str | None, candidate: CandidateInput) -> tuple[float, str] | None:
    names = [subject_name, *related_parties]
    best_name = max((name_match_score(name, candidate.name) for name in names), default=0.0)
    reasons: list[str] = []
    score = best_name
    if best_name >= 0.86:
        reasons.append("name match")
    q_email = normalize_email(email)
    c_email = normalize_email(candidate.email)
    if q_email and c_email and q_email == c_email:
        score = max(score, 1.0)
        reasons.append("exact email")
    q_phone = normalize_phone(phone)
    c_phone = normalize_phone(candidate.phone)
    if q_phone and c_phone and q_phone == c_phone:
        score = max(score, 1.0)
        reasons.append("exact phone")
    if score < 0.86:
        return None
    if candidate.restricted:
        reasons = ["possible match in restricted matter"]
    return round(score, 4), ", ".join(dict.fromkeys(reasons))


def onboarding_readiness(*, conflict_cleared: bool, identity_complete: bool, address_complete: bool, engagement_complete: bool) -> tuple[str, list[str]]:
    missing: list[str] = []
    if not conflict_cleared:
        missing.append("conflict check")
    if not identity_complete:
        missing.append("identity/KYC")
    if not address_complete:
        missing.append("address")
    if not engagement_complete:
        missing.append("engagement")
    if not missing:
        return "ready", []
    return "in_progress", missing
