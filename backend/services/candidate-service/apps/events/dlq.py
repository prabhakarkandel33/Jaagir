"""DLQ replay (ARCHITECTURE.md section 6.2).

Reads messages from ``jobs.events.v1.dlq`` and re-publishes them to
``jobs.events.v1``. The handler is idempotent (inbox + version guard), so a
replay is always safe, even when a message was partly applied before.

The replay consumer uses a throwaway group id and never commits offsets, so a
replay can be repeated. Kafka cannot delete messages, so ``replay`` means
"consume the DLQ again and re-publish"; the DLQ topic itself is not modified.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from typing import Final
from uuid import uuid4

from confluent_kafka import Consumer, Producer, TopicPartition
from django.conf import settings

from contracts import (
    HEADER_DLQ_ATTEMPTS,
    HEADER_DLQ_ERROR,
    HEADER_DLQ_FAILED_AT,
    HEADER_DLQ_SOURCE_OFFSET,
    HEADER_DLQ_SOURCE_PARTITION,
    HEADER_DLQ_SOURCE_TOPIC,
    TOPIC_JOBS_EVENTS_V1,
    TOPIC_JOBS_EVENTS_V1_DLQ,
)

logger = logging.getLogger("apps.events.dlq")

# Diagnostic headers added on the way INTO the DLQ. They must not travel back
# to the main topic, or a re-replay would stack them.
_DLQ_MARKER_HEADERS: Final[frozenset[str]] = frozenset(
    {
        HEADER_DLQ_ERROR,
        HEADER_DLQ_ATTEMPTS,
        HEADER_DLQ_SOURCE_TOPIC,
        HEADER_DLQ_SOURCE_PARTITION,
        HEADER_DLQ_SOURCE_OFFSET,
        HEADER_DLQ_FAILED_AT,
    }
)

DEFAULT_LIMIT: Final[int] = 1000
_IDLE_TIMEOUT_S: Final[float] = 5.0


Headers = Sequence[tuple[str, str | bytes | None]] | Mapping[str, str | bytes | None]


def clean_headers(headers: Headers | None) -> list[tuple[str, str | bytes | None]]:
    """Drop the DLQ diagnostic headers, keep the original event headers."""
    if headers is None:
        return []
    items = headers.items() if isinstance(headers, Mapping) else headers
    return [(key, value) for key, value in items if key not in _DLQ_MARKER_HEADERS]


def replay_dlq(*, limit: int = DEFAULT_LIMIT, dry_run: bool = False) -> dict[str, int]:
    """Re-publish up to ``limit`` DLQ messages to the main topic.

    Returns ``{"read": n, "published": n}``. With ``dry_run`` nothing is
    published.

    The read set is the DLQ size at the start of the call. A message that is
    still invalid goes back to the DLQ through the normal consumer path; this
    snapshot bound stops that from becoming an endless replay loop.
    """
    consumer = Consumer(
        {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": f"dlq-replay-{uuid4()}",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "socket.timeout.ms": 5000,
        }
    )
    producer: Producer | None = None
    if not dry_run:
        producer = Producer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "acks": "all",
                "enable.idempotence": True,
                "message.timeout.ms": settings.KAFKA_MESSAGE_TIMEOUT_MS,
            }
        )

    read = 0
    published = 0
    try:
        metadata = consumer.list_topics(TOPIC_JOBS_EVENTS_V1_DLQ, timeout=5)
        partitions = sorted(metadata.topics[TOPIC_JOBS_EVENTS_V1_DLQ].partitions)
        assignments: list[TopicPartition] = []
        snapshot = 0
        for partition in partitions:
            tp = TopicPartition(TOPIC_JOBS_EVENTS_V1_DLQ, partition)
            low, high = consumer.get_watermark_offsets(tp, timeout=5)
            snapshot += high - low
            assignments.append(tp)
        consumer.assign(assignments)
        target = min(limit, snapshot)
        deadline = time.monotonic() + _IDLE_TIMEOUT_S

        while read < target and time.monotonic() < deadline:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            error = msg.error()
            if error is not None:
                logger.warning(
                    "dlq replay poll error",
                    extra={"component": "dlq", "event": "poll_error", "error": str(error)},
                )
                continue
            read += 1
            deadline = time.monotonic() + _IDLE_TIMEOUT_S
            if producer is None:
                continue
            producer.produce(
                TOPIC_JOBS_EVENTS_V1,
                value=msg.value(),
                key=msg.key(),
                headers=clean_headers(msg.headers()),
            )
            published += 1

        if producer is not None:
            remaining = producer.flush(settings.KAFKA_MESSAGE_TIMEOUT_MS / 1000)
            if remaining:
                logger.warning(
                    "dlq replay flush timed out",
                    extra={"component": "dlq", "event": "flush_timeout", "pending": remaining},
                )
    finally:
        consumer.close()

    logger.info(
        "dlq replay finished",
        extra={"component": "dlq", "event": "replay", "read": read, "published": published},
    )
    return {"read": read, "published": published}
