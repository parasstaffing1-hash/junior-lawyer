from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AICitationStatus, AIClaimStatus
from app.services.research.citations import parse_citations
from app.services.research.service import verify_citation

SOURCE_REF_RE = re.compile(r"\[S(?P<number>\d+)\]")
CLAIM_PIECE_RE = re.compile(r".+?(?:[.!?।](?:\s*(?:\[S\d+\]))*|$)(?=\s|$)")
WORD_RE = re.compile(r"[A-Za-z0-9]+|[\u0900-\u097F]+")

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "are", "was", "were",
    "that", "this", "with", "from", "by", "as", "be", "it", "at", "has", "have", "had", "may",
    "का", "की", "के", "में", "से", "को", "और", "है", "हैं", "था", "थी", "पर", "यह", "कि",
}


@dataclass(slots=True)
class ClaimAudit:
    ordinal: int
    claim_text: str
    substantive: bool
    cited_source_keys: list[str]
    support_score: float
    status: AIClaimStatus
    explanation: str | None


@dataclass(slots=True)
class CitationAudit:
    raw_citation: str
    normalized_citation: str | None
    status: AICitationStatus
    matched_judgment_id: UUID | None
    cited_source_keys: list[str]
    metadata: dict


@dataclass(slots=True)
class VerificationResult:
    status: str
    claims: list[ClaimAudit]
    citations: list[CitationAudit]
    summary: dict


def audit_claims(response_text: str, sources: list[object]) -> list[ClaimAudit]:
    source_map = {getattr(source, "source_key"): source for source in sources}
    pieces: list[str] = []
    for line in response_text.splitlines():
        line = line.strip()
        if not line:
            continue
        matches = [m.group(0).strip(" -\t") for m in CLAIM_PIECE_RE.finditer(line) if m.group(0).strip()]
        pieces.extend(matches or [line.strip(" -\t")])
    audits: list[ClaimAudit] = []
    ordinal = 0
    for piece in pieces:
        if piece.startswith("#") and len(WORD_RE.findall(piece)) <= 7:
            continue
        ordinal += 1
        refs = [f"S{match.group('number')}" for match in SOURCE_REF_RE.finditer(piece)]
        refs = list(dict.fromkeys(refs))
        substantive = _is_substantive(piece)
        if not substantive:
            audits.append(ClaimAudit(ordinal, piece, False, refs, 0.0, AIClaimStatus.NON_SUBSTANTIVE, None))
            continue
        invalid = [ref for ref in refs if ref not in source_map]
        if invalid:
            audits.append(ClaimAudit(
                ordinal, piece, True, refs, 0.0, AIClaimStatus.INVALID_SOURCE,
                f"Unknown source key(s): {', '.join(invalid)}",
            ))
            continue
        if not refs:
            audits.append(ClaimAudit(
                ordinal, piece, True, [], 0.0, AIClaimStatus.UNCITED,
                "Substantive proposition has no inline source marker.",
            ))
            continue
        score = max((_overlap_score(piece, getattr(source_map[ref], "text")) for ref in refs), default=0.0)
        if score < 0.045:
            audits.append(ClaimAudit(
                ordinal, piece, True, refs, round(score, 4), AIClaimStatus.WEAK_SUPPORT,
                "Cited source has low lexical overlap; lawyer should verify the proposition against the source.",
            ))
        else:
            audits.append(ClaimAudit(ordinal, piece, True, refs, round(score, 4), AIClaimStatus.SUPPORTED, None))
    return audits


async def audit_reported_citations(
    db: AsyncSession,
    response_text: str,
    sources: list[object],
) -> list[CitationAudit]:
    audits: list[CitationAudit] = []
    for parsed in parse_citations(response_text):
        result = await verify_citation(db, parsed.raw)
        matches = result.get("matches") or []
        if result.get("status") == "resolved":
            status = AICitationStatus.RESOLVED
        elif result.get("status") == "ambiguous":
            status = AICitationStatus.AMBIGUOUS
        else:
            status = AICitationStatus.UNRESOLVED
        matched = UUID(str(matches[0]["judgment_id"])) if len(matches) == 1 else None
        nearby_refs = _refs_near_text(response_text, parsed.raw)
        audits.append(CitationAudit(
            raw_citation=parsed.raw,
            normalized_citation=result.get("normalized") or parsed.normalized,
            status=status,
            matched_judgment_id=matched,
            cited_source_keys=nearby_refs,
            metadata={"reporter": parsed.reporter, "matches": len(matches)},
        ))
    return audits


async def verify_response(db: AsyncSession, response_text: str, sources: list[object]) -> VerificationResult:
    claims = audit_claims(response_text, sources)
    citations = await audit_reported_citations(db, response_text, sources)
    counts = {status.value: 0 for status in AIClaimStatus}
    for claim in claims:
        counts[claim.status.value] = counts.get(claim.status.value, 0) + 1
    citation_counts = {status.value: 0 for status in AICitationStatus}
    for citation in citations:
        citation_counts[citation.status.value] = citation_counts.get(citation.status.value, 0) + 1

    hard_fail = counts.get(AIClaimStatus.INVALID_SOURCE.value, 0) > 0 or citation_counts.get(AICitationStatus.UNRESOLVED.value, 0) > 0
    warnings = (
        counts.get(AIClaimStatus.UNCITED.value, 0)
        + counts.get(AIClaimStatus.WEAK_SUPPORT.value, 0)
        + citation_counts.get(AICitationStatus.AMBIGUOUS.value, 0)
    )
    status = "failed" if hard_fail else ("warnings" if warnings else "passed")
    return VerificationResult(
        status=status,
        claims=claims,
        citations=citations,
        summary={
            "claim_counts": counts,
            "citation_counts": citation_counts,
            "invalid_source_refs": counts.get(AIClaimStatus.INVALID_SOURCE.value, 0),
            "uncited_claims": counts.get(AIClaimStatus.UNCITED.value, 0),
            "weak_support_claims": counts.get(AIClaimStatus.WEAK_SUPPORT.value, 0),
            "unresolved_reported_citations": citation_counts.get(AICitationStatus.UNRESOLVED.value, 0),
            "ambiguous_reported_citations": citation_counts.get(AICitationStatus.AMBIGUOUS.value, 0),
        },
    )


def _is_substantive(text: str) -> bool:
    cleaned = SOURCE_REF_RE.sub("", text).strip()
    lower = cleaned.casefold()
    if any(phrase in lower for phrase in (
        "not established from the provided sources",
        "lawyer review",
        "provided sources are insufficient",
        "वकील द्वारा समीक्षा",
    )):
        return False
    words = WORD_RE.findall(cleaned)
    return len(words) >= 5


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in WORD_RE.findall(SOURCE_REF_RE.sub("", text)) if token.casefold() not in STOPWORDS and len(token) > 1}


def _overlap_score(claim: str, source: str) -> float:
    a, b = _tokens(claim), _tokens(source)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def _refs_near_text(text: str, needle: str, radius: int = 180) -> list[str]:
    pos = text.find(needle)
    if pos < 0:
        return []
    window = text[max(0, pos - radius): min(len(text), pos + len(needle) + radius)]
    return list(dict.fromkeys(f"S{m.group('number')}" for m in SOURCE_REF_RE.finditer(window)))
