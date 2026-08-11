from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from app.core.config import settings


_PREFIX = "scrypt-v1"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(
    password: str,
    *,
    n: int | None = None,
    r: int | None = None,
    p: int | None = None,
    dklen: int | None = None,
    salt: bytes | None = None,
) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    n = n or settings.security_scrypt_n
    r = r or settings.security_scrypt_r
    p = p or settings.security_scrypt_p
    dklen = dklen or settings.security_scrypt_dklen
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen)
    return f"{_PREFIX}${n}${r}${p}${dklen}${_b64(salt)}${_b64(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        prefix, n, r, p, dklen, salt, expected = encoded.split("$", 6)
        if prefix != _PREFIX:
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=int(dklen),
        )
        return hmac.compare_digest(derived, _unb64(expected))
    except (ValueError, TypeError):
        return False


def new_session_token() -> str:
    # 32 random bytes => 256 bits before URL-safe encoding.
    return secrets.token_urlsafe(32)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token_hash(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(token_hash(token), expected_hash)


def privacy_hash(value: str | None) -> str | None:
    if not value:
        return None
    key = settings.security_privacy_hash_key
    if key:
        return hmac.new(key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
