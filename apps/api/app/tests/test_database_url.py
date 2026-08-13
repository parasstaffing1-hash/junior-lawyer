"""Connection strings as managed Postgres providers actually issue them."""

import pytest

from app.db.url import prepare_database_url

# The shape Aiven hands out in its console.
AIVEN = "postgres://avnadmin:secret@pg-example-project.a.aivencloud.com:23456/defaultdb?sslmode=require"


def test_an_aiven_url_becomes_usable_in_one_step():
    target = prepare_database_url(AIVEN)
    # Driver-qualified, because create_async_engine cannot infer one.
    assert target.url.startswith("postgresql+asyncpg://")
    # sslmode is libpq-only and makes asyncpg raise TypeError; it moves across
    # to the connect args, where asyncpg expects it.
    assert "sslmode" not in target.url
    assert target.connect_args == {"ssl": "require"}
    # Credentials, host, port and database survive untouched.
    assert "avnadmin:secret@pg-example-project.a.aivencloud.com:23456/defaultdb" in target.url


def test_the_legacy_postgres_scheme_is_corrected():
    # SQLAlchemy dropped `postgres://` in 1.4; several providers still emit it.
    target = prepare_database_url("postgres://u:p@host:5432/db")
    assert target.url == "postgresql+asyncpg://u:p@host:5432/db"


def test_an_explicit_driver_is_respected():
    target = prepare_database_url("postgresql+psycopg://u:p@host:5432/db")
    assert target.url.startswith("postgresql+psycopg://")
    # Only asyncpg needs the sslmode translation, so other drivers keep libpq
    # parameters as they are.
    kept = prepare_database_url("postgresql+psycopg://u:p@host/db?sslmode=require")
    assert "sslmode=require" in kept.url
    assert kept.connect_args == {}


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("require", "require"),
        ("verify-full", "verify-full"),
        ("verify-ca", "verify-ca"),
        ("prefer", "prefer"),
        ("allow", "prefer"),
    ],
)
def test_every_ssl_mode_survives_rather_than_collapsing_to_one(mode, expected):
    # Downgrading verify-full to "encrypted but unverified" would silently
    # weaken a deliberately strict configuration.
    target = prepare_database_url(f"postgres://u:p@host/db?sslmode={mode}")
    assert target.connect_args == {"ssl": expected}


def test_ssl_disabled_means_no_ssl_argument():
    assert prepare_database_url("postgres://u:p@host/db?sslmode=disable").connect_args == {}


def test_an_unknown_ssl_mode_is_rejected_loudly():
    with pytest.raises(ValueError, match="Unrecognised sslmode"):
        prepare_database_url("postgres://u:p@host/db?sslmode=maybe")


def test_other_query_parameters_are_preserved():
    target = prepare_database_url(
        "postgres://u:p@host/db?sslmode=require&application_name=junior-lawyer"
    )
    assert "application_name=junior-lawyer" in target.url


def test_sqlite_is_left_exactly_as_configured():
    raw = "sqlite+aiosqlite:///./junior_lawyer_dev.db"
    target = prepare_database_url(raw)
    assert target.url == raw
    assert target.is_sqlite
    assert target.connect_args == {}


def test_an_empty_url_fails_with_a_clear_message():
    with pytest.raises(ValueError, match="DATABASE_URL is empty"):
        prepare_database_url("   ")
