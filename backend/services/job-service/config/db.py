"""Build a Django DATABASES entry from a Postgres DSN."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from pydantic import PostgresDsn


def database_config(dsn: PostgresDsn) -> dict:
    """Return a Django ``DATABASES['default']`` mapping for a Postgres DSN.

    ``PostgresDsn`` is stringified and parsed with ``urllib`` so this works
    across pydantic versions (the v1 ``.parsed`` attribute is gone in v2).
    """
    parsed = urlparse(str(dsn))
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": 60,
    }
