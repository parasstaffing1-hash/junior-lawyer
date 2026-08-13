"""Turn a hosting provider's connection string into one SQLAlchemy can use.

Managed Postgres (Aiven, Render, Heroku, Supabase) hands out a libpq URL:

    postgres://user:pass@host:12345/defaultdb?sslmode=require

That string fails three different ways here, and each failure looks unrelated
to the others:

  * `postgres://` is not a SQLAlchemy dialect name — it was removed in 1.4.
  * With no driver, SQLAlchemy reaches for psycopg2, which is not a dependency
    of this project and cannot drive an async engine anyway.
  * `sslmode` is a libpq parameter. asyncpg takes `ssl` instead and raises
    TypeError on an unexpected keyword, so the connection dies at the last
    step — after the URL looks correct.

Normalising in one place means the app, Alembic and any script share exactly
one interpretation of the setting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Schemes a provider might hand out for the same thing.
_POSTGRES_SCHEMES = {"postgres", "postgresql"}
# libpq spellings mapped to what asyncpg understands. asyncpg accepts these as
# strings directly, so the operator's intent survives rather than being
# flattened to "encrypted, unverified".
_SSL_MODES = {
    "disable": "disable",
    "allow": "prefer",
    "prefer": "prefer",
    "require": "require",
    "verify-ca": "verify-ca",
    "verify-full": "verify-full",
}


@dataclass(frozen=True)
class DatabaseTarget:
    url: str
    connect_args: dict = field(default_factory=dict)

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")


def prepare_database_url(raw: str) -> DatabaseTarget:
    """Return a driver-qualified URL plus the connect args it implies."""
    candidate = (raw or "").strip()
    if not candidate:
        raise ValueError("DATABASE_URL is empty")

    parts = urlsplit(candidate)
    scheme, _, driver = parts.scheme.partition("+")

    if scheme not in _POSTGRES_SCHEMES:
        # SQLite and anything already explicit is left exactly as configured.
        return DatabaseTarget(url=candidate)

    # asyncpg is the only Postgres driver this project depends on.
    driver = driver or "asyncpg"

    query = parse_qsl(parts.query, keep_blank_values=True)
    connect_args: dict = {}
    remaining: list[tuple[str, str]] = []
    for key, value in query:
        lowered = key.lower()
        if lowered in {"sslmode", "ssl"} and driver == "asyncpg":
            mode = _SSL_MODES.get(value.lower())
            if mode is None:
                raise ValueError(f"Unrecognised sslmode in DATABASE_URL: {value!r}")
            if mode != "disable":
                connect_args["ssl"] = mode
        elif lowered == "channel_binding" and driver == "asyncpg":
            # libpq-only; asyncpg negotiates this itself.
            continue
        else:
            remaining.append((key, value))

    rebuilt = urlunsplit(
        (f"postgresql+{driver}", parts.netloc, parts.path, urlencode(remaining), parts.fragment)
    )
    return DatabaseTarget(url=rebuilt, connect_args=connect_args)
