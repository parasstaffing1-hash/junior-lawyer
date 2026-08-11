from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def allowed_source_host(url: str, allowed_domains: list[str]) -> tuple[bool, str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https":
        return False, host
    domains = [str(item).casefold().strip().rstrip(".") for item in allowed_domains if str(item).strip()]
    if not host or not domains:
        return False, host
    return any(host == domain or host.endswith("." + domain) for domain in domains), host


def is_stale(last_success_at: datetime | None, stale_after_hours: int, *, now: datetime | None = None) -> bool:
    if last_success_at is None:
        return True
    current = now or utcnow()
    if last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=timezone.utc)
    return current - last_success_at > timedelta(hours=max(1, stale_after_hours))


def next_due(last_checked_at: datetime | None, interval_minutes: int, *, now: datetime | None = None) -> datetime:
    current = now or utcnow()
    if last_checked_at is None:
        return current
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=timezone.utc)
    return last_checked_at + timedelta(minutes=max(5, interval_minutes))


def classify_hash_change(before_sha256: str | None, after_sha256: str) -> str:
    if not before_sha256:
        return "new"
    return "unchanged" if before_sha256.casefold() == after_sha256.casefold() else "updated"


def section_snapshot(section: object) -> dict:
    return {
        "section_number": getattr(section, "section_number", None),
        "provision_type": getattr(section, "provision_type", None),
        "heading_en": getattr(section, "heading_en", None),
        "heading_hi": getattr(section, "heading_hi", None),
        "text_en": getattr(section, "text_en", None),
        "text_hi": getattr(section, "text_hi", None),
        "effective_from": getattr(section, "effective_from", None),
        "effective_to": getattr(section, "effective_to", None),
        "version_label": getattr(section, "version_label", None),
        "source_hash": getattr(section, "source_hash", None),
    }


def section_payload_snapshot(section: object) -> dict:
    data = section.model_dump(mode="json") if hasattr(section, "model_dump") else dict(section)
    return {
        "section_number": data.get("section_number"),
        "provision_type": data.get("provision_type", "section"),
        "heading_en": data.get("heading_en"),
        "heading_hi": data.get("heading_hi"),
        "text_en": data.get("text_en"),
        "text_hi": data.get("text_hi"),
        "effective_from": data.get("effective_from"),
        "effective_to": data.get("effective_to"),
        "version_label": data.get("version_label"),
    }


def section_content_hash(snapshot: dict) -> str:
    return canonical_sha256({k: snapshot.get(k) for k in ("section_number", "provision_type", "heading_en", "heading_hi", "text_en", "text_hi")})


def release_manifest_hash(*, pack_key: str, version: str, effective_from: object, effective_to: object, sources: list[dict]) -> str:
    clean_sources = sorted(
        [
            {
                "source_id": str(s.get("source_id")),
                "feed_id": str(s.get("feed_id")) if s.get("feed_id") else None,
                "required": bool(s.get("required", True)),
                "maximum_age_hours": int(s.get("maximum_age_hours", 72)),
            }
            for s in sources
        ],
        key=lambda x: (x["source_id"], x["feed_id"] or ""),
    )
    return canonical_sha256({"pack_key": pack_key, "version": version, "effective_from": effective_from, "effective_to": effective_to, "sources": clean_sources})
