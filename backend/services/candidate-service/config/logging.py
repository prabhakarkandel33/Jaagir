"""JSON logging with redaction (invariant I6: never log secrets)."""

from __future__ import annotations

import json
import logging
from typing import Any

from config.observability import get_request_id

# Any log key whose lowercase name contains one of these is masked.
SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "set-cookie",
    "refresh",
)

REDACTED = "***redacted***"

# LogRecord attributes we do not copy into the JSON payload.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}


def _redact(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return REDACTED
    return value


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per record, with sensitive values masked."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id:
            payload["requestId"] = request_id

        for key, value in record.__dict__.items():
            if key in _RESERVED:
                continue
            payload[key] = _redact(key, value)

        if record.exc_info:
            payload["excInfo"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def build_logging_config(level: str) -> dict[str, Any]:
    """Return a ``LOGGING`` dict for Django settings."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": "config.logging.JsonFormatter"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        },
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            "django": {"handlers": ["console"], "level": level, "propagate": False},
            "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
            "gunicorn.error": {"handlers": ["console"], "level": level, "propagate": False},
            "gunicorn.access": {"handlers": ["console"], "level": level, "propagate": False},
        },
    }
