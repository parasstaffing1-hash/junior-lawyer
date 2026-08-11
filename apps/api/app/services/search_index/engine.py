from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from app.services.language.normalizer import normalize_legal_text
from app.services.research.ranking import expand_query

TOKEN_RE = re.compile(r"[\w\u0900-\u097f]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    normalized = normalize_legal_text(text or "").casefold()
    return [m.group(0) for m in TOKEN_RE.finditer(normalized) if len(m.group(0)) > 1]


def content_hash(text: str) -> str:
    normalized = " ".join((text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def simhash64(text: str) -> str:
    tokens = tokenize(text)
    if not tokens:
        return "0" * 16
    counts = Counter(tokens)
    vector = [0] * 64
    for token, weight in counts.items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        for bit in range(64):
            vector[bit] += weight if value & (1 << bit) else -weight
    out = 0
    for bit, score in enumerate(vector):
        if score >= 0:
            out |= 1 << bit
    return f"{out:016x}"


def hamming_distance(left: str, right: str) -> int:
    return (int(left or "0", 16) ^ int(right or "0", 16)).bit_count()


def simhash_bands(value: str, bands: int = 4) -> tuple[str, ...]:
    """Return LSH band keys so near-duplicate detection avoids an O(n²) corpus scan."""
    raw = f"{int(value or '0', 16):016x}"
    width = max(1, 16 // bands)
    return tuple(f"{idx}:{raw[idx * width:(idx + 1) * width]}" for idx in range(bands))


def shingles(text: str, size: int = 3) -> set[tuple[str, ...]]:
    tokens = tokenize(text)
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


def shingle_jaccard(left: str, right: str, size: int = 3) -> float:
    a, b = shingles(left, size), shingles(right, size)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def feature_vector(text: str, dimensions: int = 128, *, expand_legal: bool = True) -> list[float]:
    """Local zero-cost feature hashing vector.

    This is intentionally a deterministic fallback, not a claim of transformer-level semantic embeddings.
    Query expansion supplies Hindi/English legal equivalences; deployments can later swap in a local
    multilingual embedding server without changing the persisted index contract.
    """
    if expand_legal:
        _, expanded = expand_query(text)
        tokens = tokenize(" ".join(expanded) if expanded else text)
    else:
        tokens = tokenize(text)
    vector = [0.0] * dimensions
    if not tokens:
        return vector
    counts = Counter(tokens)
    for token, count in counts.items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        raw = int.from_bytes(digest, "big")
        slot = raw % dimensions
        sign = 1.0 if (raw >> 63) == 0 else -1.0
        vector[slot] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 7) for v in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    ln = math.sqrt(sum(a * a for a in left))
    rn = math.sqrt(sum(b * b for b in right))
    if not ln or not rn:
        return 0.0
    return max(0.0, min(1.0, dot / (ln * rn)))


def chunk_text(text: str, *, max_chars: int = 1800, overlap: int = 180) -> list[str]:
    clean = "\n".join(line.strip() for line in (text or "").splitlines() if line.strip())
    if not clean:
        return []
    if len(clean) <= max_chars:
        return [clean]
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + max_chars)
        if end < len(clean):
            boundary = max(clean.rfind("\n", start + max_chars // 2, end), clean.rfind(". ", start + max_chars // 2, end))
            if boundary > start:
                end = boundary + 1
        part = clean[start:end].strip()
        if part:
            chunks.append(part)
        if end >= len(clean):
            break
        start = max(start + 1, end - overlap)
    return chunks


@dataclass(slots=True)
class DuplicateScore:
    exact: bool
    near: bool
    hamming: int
    jaccard: float
    similarity: float


def duplicate_score(left: str, right: str, *, max_hamming: int = 6, min_jaccard: float = 0.82) -> DuplicateScore:
    exact = content_hash(left) == content_hash(right)
    hamming = hamming_distance(simhash64(left), simhash64(right))
    jaccard = shingle_jaccard(left, right)
    near = (not exact) and hamming <= max_hamming and jaccard >= min_jaccard
    similarity = 1.0 if exact else round((1 - hamming / 64) * 0.35 + jaccard * 0.65, 6)
    return DuplicateScore(exact=exact, near=near, hamming=hamming, jaccard=round(jaccard, 6), similarity=similarity)


def index_document_chunks(text: str) -> Iterable[tuple[int, str]]:
    for idx, chunk in enumerate(chunk_text(text), start=1):
        yield idx, chunk
