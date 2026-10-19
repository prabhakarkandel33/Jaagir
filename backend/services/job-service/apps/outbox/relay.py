"""Outbox relay (ARCHITECTURE.md section 6.1).

Only the relay publishes outbox rows to Kafka. One active relay at a time
(Postgres advisory lock); it drains rows in id order with ``FOR UPDATE SKIP
LOCKED``, stops the batch on the first failure (to preserve per-job order) and
backs off with capped exponential delay. Delivery is at-least-once.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, runtime_checkable

from django.db import connection, transaction
from django.utils import timezone

from apps.outbox.models import OutboxEvent
from contracts import (
    HEADER_EVENT_ID,
    HEADER_EVENT_TYPE,
    HEADER_SCHEMA_VERSION,
    TOPIC_JOBS_EVENTS_V1,
)

logger = logging.getLogger("apps.outbox.relay")

RELAY_BATCH_SIZE = 100
BACKOFF_CAP_SECONDS = 30
# Arbitrary constant; must match in every relay process.
ADVISORY_LOCK_KEY = 4_242_001


@runtime_checkable
class Publisher(Protocol):
    def publish(
        self,
        topic: str,
        value: bytes,
        key: str,
        headers: Sequence[tuple[str, bytes]],
    ) -> None: ...


@dataclass(frozen=True)
class RelayResult:
    locked: bool
    published: int
    failed: int
    error: str | None = None


def backoff_seconds(attempts: int) -> int:
    return min(2 ** min(attempts, 5), BACKOFF_CAP_SECONDS)


def _try_advisory_lock() -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [ADVISORY_LOCK_KEY])
        row = cursor.fetchone()
    return bool(row and row[0])


def _release_advisory_lock() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])


def _headers_for(row: OutboxEvent) -> list[tuple[str, bytes]]:
    envelope = row.payload if isinstance(row.payload, dict) else {}
    return [
        (HEADER_EVENT_TYPE, str(envelope.get("eventType", row.event_type)).encode()),
        (HEADER_EVENT_ID, str(row.event_id).encode()),
        (HEADER_SCHEMA_VERSION, str(envelope.get("schemaVersion", 1)).encode()),
    ]


def _value_bytes(row: OutboxEvent) -> bytes:
    return json.dumps(row.payload, separators=(",", ":"), default=str).encode("utf-8")


def _record_failure(row: OutboxEvent, error: str) -> None:
    row.attempts += 1
    row.last_error = error[:500]
    row.next_attempt_at = timezone.now() + timedelta(seconds=backoff_seconds(row.attempts))
    row.save(update_fields=["attempts", "last_error", "next_attempt_at"])
    logger.warning(
        "outbox publish failed",
        extra={
            "component": "relay",
            "event": "publish_failed",
            "eventId": str(row.event_id),
            "aggregateId": str(row.aggregate_id),
            "attempts": row.attempts,
            "error": error,
        },
    )


def relay_once(publisher: Publisher, *, batch: int = RELAY_BATCH_SIZE) -> RelayResult:
    """Run one relay cycle. Safe to call concurrently (advisory lock)."""
    if not _try_advisory_lock():
        return RelayResult(locked=False, published=0, failed=0)
    try:
        return _drain(publisher, batch=batch)
    finally:
        _release_advisory_lock()


def _drain(publisher: Publisher, *, batch: int) -> RelayResult:
    now = timezone.now()
    published = 0
    failed = 0
    last_error: str | None = None

    with transaction.atomic():
        rows = list(
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(published_at__isnull=True, next_attempt_at__lte=now)
            .order_by("id")[:batch]
        )
        for row in rows:
            try:
                publisher.publish(
                    TOPIC_JOBS_EVENTS_V1,
                    _value_bytes(row),
                    str(row.aggregate_id),
                    _headers_for(row),
                )
            except Exception as exc:
                _record_failure(row, str(exc))
                failed += 1
                last_error = str(exc)
                # Stop the batch: keep per-aggregate ordering, retry next cycle.
                break

            row.published_at = timezone.now()
            row.last_error = None
            row.save(update_fields=["published_at", "last_error"])
            published += 1
            logger.info(
                "outbox published",
                extra={
                    "component": "relay",
                    "event": "published",
                    "eventId": str(row.event_id),
                    "aggregateId": str(row.aggregate_id),
                    "aggregateVersion": row.aggregate_version,
                },
            )

    if published or failed:
        logger.info(
            "relay cycle done",
            extra={
                "component": "relay",
                "event": "cycle",
                "published": published,
                "failed": failed,
            },
        )
    return RelayResult(locked=True, published=published, failed=failed, error=last_error)
