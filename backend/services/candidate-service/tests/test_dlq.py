"""DLQ helpers (M6).

The network part of the replay is exercised by the e2e suite; here we pin the
header contract: diagnostic headers must not travel back to the main topic.
"""

from __future__ import annotations

from apps.events.dlq import clean_headers
from contracts import (
    HEADER_DLQ_ATTEMPTS,
    HEADER_DLQ_ERROR,
    HEADER_DLQ_SOURCE_OFFSET,
    HEADER_EVENT_ID,
    HEADER_EVENT_TYPE,
)


def test_clean_headers_keeps_event_headers() -> None:
    headers: list[tuple[str, str | bytes | None]] = [
        (HEADER_EVENT_TYPE, b"JobPublished"),
        (HEADER_EVENT_ID, b"abc"),
    ]
    assert clean_headers(headers) == headers


def test_clean_headers_drops_dlq_diagnostics() -> None:
    headers: list[tuple[str, str | bytes | None]] = [
        (HEADER_EVENT_TYPE, b"JobPublished"),
        (HEADER_DLQ_ERROR, b"boom"),
        (HEADER_DLQ_ATTEMPTS, b"3"),
        (HEADER_DLQ_SOURCE_OFFSET, b"42"),
    ]
    assert clean_headers(headers) == [(HEADER_EVENT_TYPE, b"JobPublished")]


def test_clean_headers_handles_none() -> None:
    assert clean_headers(None) == []
