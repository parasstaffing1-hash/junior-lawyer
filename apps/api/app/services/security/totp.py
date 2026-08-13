"""RFC 6238 time-based one-time passwords.

Implemented directly rather than pulled in as a dependency: the algorithm is
thirty lines of HMAC, and authenticator enrolment is a security boundary we
would rather read than trust.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITS = 6
PERIOD_SECONDS = 30
# One step either side, so a code entered as the window rolls is still accepted.
DEFAULT_DRIFT_STEPS = 1


def new_secret() -> str:
    """A fresh base32 secret, the format every authenticator app expects."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode(secret: str) -> bytes:
    padded = secret.strip().replace(" ", "").upper()
    return base64.b32decode(padded + "=" * (-len(padded) % 8), casefold=True)


def code_for_counter(secret: str, counter: int) -> str:
    digest = hmac.new(_decode(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    (truncated,) = struct.unpack(">I", digest[offset : offset + 4])
    return str((truncated & 0x7FFFFFFF) % (10**DIGITS)).zfill(DIGITS)


def counter_at(moment: float | None = None) -> int:
    return int((moment if moment is not None else time.time()) // PERIOD_SECONDS)


def verify(
    secret: str,
    code: str,
    *,
    at: float | None = None,
    drift_steps: int = DEFAULT_DRIFT_STEPS,
    last_used_counter: int | None = None,
) -> int | None:
    """Return the counter the code belongs to, or None if it is not valid.

    Callers persist the returned counter and pass it back as
    `last_used_counter`, which is what stops a code being replayed inside its
    own thirty-second window.
    """
    candidate = (code or "").strip().replace(" ", "")
    if not candidate.isdigit() or len(candidate) != DIGITS:
        return None
    current = counter_at(at)
    for step in range(-drift_steps, drift_steps + 1):
        counter = current + step
        if counter < 0:
            continue
        if last_used_counter is not None and counter <= last_used_counter:
            continue
        if hmac.compare_digest(code_for_counter(secret, counter), candidate):
            return counter
    return None


def provisioning_uri(secret: str, *, account: str, issuer: str) -> str:
    """otpauth:// URI for QR enrolment."""
    label = quote(f"{issuer}:{account}", safe="")
    return (
        f"otpauth://totp/{label}?secret={secret}"
        f"&issuer={quote(issuer, safe='')}&algorithm=SHA1&digits={DIGITS}&period={PERIOD_SECONDS}"
    )


def new_recovery_codes(count: int = 10) -> list[str]:
    """Single-use codes for when the authenticator device is lost."""
    return ["-".join(secrets.token_hex(2) for _ in range(3)) for _ in range(count)]
