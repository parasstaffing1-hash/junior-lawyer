from app.services.security.crypto import (
    hash_password,
    new_csrf_token,
    new_session_token,
    token_hash,
    verify_password,
    verify_token_hash,
)


def test_scrypt_password_hash_round_trip_and_salts():
    first = hash_password("correct horse battery staple", n=1024, r=8, p=1)
    second = hash_password("correct horse battery staple", n=1024, r=8, p=1)
    assert first.startswith("scrypt-v1$")
    assert first != second
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong password", first)


def test_session_and_csrf_tokens_are_opaque_and_hashed():
    session = new_session_token()
    csrf = new_csrf_token()
    assert session != csrf
    assert len(session) >= 40
    assert len(csrf) >= 40
    digest = token_hash(session)
    assert len(digest) == 64
    assert session not in digest
    assert verify_token_hash(session, digest)
    assert not verify_token_hash(session + "x", digest)
