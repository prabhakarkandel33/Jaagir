"""Kafka consumer for the Candidate Service (ARCHITECTURE.md section 6.2).

Design constraints:

- **Kafka is optional for availability (invariant I9).** Nothing connects at
  import time; the consumer command retries in the background and reports
  ``up``/``degraded``.
- **Never block a partition.** A poison message is routed to the DLQ and the
  offset is committed; the loop never rethrows.
- Per message, in one DB transaction: inbox insert + version-guarded upsert.
  Transient errors retry 3 times with backoff; validation errors are
  non-retryable and go straight to the DLQ.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from functools import lru_cache
from typing import Final, cast

from confluent_kafka import Consumer, KafkaError, KafkaException, Message, Producer
from confluent_kafka.admin import AdminClient, NewTopic
from django.utils import timezone
from pydantic import ValidationError

from apps.events.models import ConsumerStatus
from apps.events.services import DUPLICATE, apply_envelope
from contracts import (
    HEADER_DLQ_ATTEMPTS,
    HEADER_DLQ_ERROR,
    HEADER_DLQ_FAILED_AT,
    HEADER_DLQ_SOURCE_OFFSET,
    HEADER_DLQ_SOURCE_PARTITION,
    HEADER_DLQ_SOURCE_TOPIC,
    TOPIC_JOBS_EVENTS_V1,
    TOPIC_JOBS_EVENTS_V1_DLQ,
    EventEnvelope,
    parse_envelope,
)
from contracts.envelope import UnsupportedSchemaVersionError

logger = logging.getLogger("apps.events.consumer")

STATUS_UNKNOWN: Final[str] = "unknown"
STATUS_UP: Final[str] = "up"
STATUS_DEGRADED: Final[str] = "degraded"

# 3 attempts for transient errors: 200 ms / 1 s / 5 s (ARCHITECTURE.md 6.2).
RETRY_BACKOFF_S: Final[tuple[float, ...]] = (0.2, 1.0, 5.0)

# Non-retryable: the message can never be applied, send it to the DLQ.
_NON_RETRYABLE = (ValidationError, UnsupportedSchemaVersionError, ValueError, json.JSONDecodeError)


class EventConsumer:
    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        *,
        operation_timeout_s: float = 5.0,
        message_timeout_ms: int = 5000,
    ) -> None:
        self._bootstrap = bootstrap_servers
        self._group_id = group_id
        self._operation_timeout_s = operation_timeout_s
        self._message_timeout_ms = message_timeout_ms

        self._consumer: Consumer | None = None
        self._producer: Producer | None = None
        self._admin_client: AdminClient | None = None
        self._topics_ensured = False

        self._status = STATUS_UNKNOWN
        self._last_error: str | None = None
        self.processed = 0
        self.duplicates = 0
        self.dlq_count = 0

    # -- status -----------------------------------------------------------
    @property
    def status(self) -> str:
        return self._status

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _set_status(self, status: str, error: str | None) -> None:
        if status == self._status and error == self._last_error:
            return
        self._status = status
        self._last_error = error
        logger.info(
            "consumer status changed",
            extra={"component": "consumer", "event": "status", "status": status, "error": error},
        )
        self._write_status()

    def _write_status(self) -> None:
        """Upsert the heartbeat row the HTTP process reads for /readyz.

        The consumer is its own process, so status must leave the process via
        the DB. A write failure must never stop the loop (invariant I9).
        """
        try:
            ConsumerStatus.objects.update_or_create(
                id=1,
                defaults={
                    "status": self._status,
                    "last_error": self._last_error,
                    "processed": self.processed,
                    "dlq_count": self.dlq_count,
                    "last_heartbeat_at": timezone.now(),
                },
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "consumer heartbeat write failed",
                extra={"component": "consumer", "error": str(exc)},
            )

    # -- lifecycle --------------------------------------------------------
    def _admin(self) -> AdminClient:
        # Hold ONE AdminClient: a temporary one is GC'd before create_topics
        # futures resolve (CONTEXT.md gotcha, [2026-10-19, M3]).
        if self._admin_client is None:
            self._admin_client = AdminClient({"bootstrap.servers": self._bootstrap})
        return self._admin_client

    def _ensure_topics(self) -> None:
        futures = self._admin().create_topics(
            [NewTopic(TOPIC_JOBS_EVENTS_V1_DLQ, num_partitions=1, replication_factor=1)],
            operation_timeout=self._operation_timeout_s,
            request_timeout=self._operation_timeout_s,
        )
        for name, future in futures.items():
            try:
                future.result(timeout=self._operation_timeout_s)
            except KafkaException as exc:
                code = exc.args[0].code() if exc.args else None
                if code != KafkaError.TOPIC_ALREADY_EXISTS:
                    raise
            logger.info(
                "kafka topic ready",
                extra={"component": "consumer", "event": "topic_ready", "topic": name},
            )

    def _build_consumer(self) -> Consumer:
        return Consumer(
            {
                "bootstrap.servers": self._bootstrap,
                "group.id": self._group_id,
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
                "enable.partition.eof": False,
                "socket.timeout.ms": int(self._operation_timeout_s * 1000),
            }
        )

    def _build_producer(self) -> Producer:
        return Producer(
            {
                "bootstrap.servers": self._bootstrap,
                "acks": "all",
                "enable.idempotence": True,
                "message.timeout.ms": self._message_timeout_ms,
            }
        )

    def ensure_ready(self) -> None:
        """Create topics, build the consumer and subscribe. Raises on failure."""
        if self._producer is None:
            self._producer = self._build_producer()
        if not self._topics_ensured:
            self._ensure_topics()
            self._topics_ensured = True
        self._admin().list_topics(timeout=self._operation_timeout_s)
        if self._consumer is None:
            self._consumer = self._build_consumer()
            self._consumer.subscribe([TOPIC_JOBS_EVENTS_V1])
        self._set_status(STATUS_UP, None)

    def close(self) -> None:
        if self._consumer is not None:
            try:
                self._consumer.close()
            except Exception:
                logger.warning("consumer close failed", exc_info=True)
            self._consumer = None

    # -- main loop --------------------------------------------------------
    def run(self, stop: threading.Event, poll_interval_s: float = 1.0) -> None:
        """Poll, process and commit until ``stop`` is set. Never rethrows."""
        try:
            self.ensure_ready()
        except Exception as exc:  # broker down at boot; retry in the loop
            self._set_status(STATUS_DEGRADED, str(exc))

        while not stop.is_set():
            consumer = self._consumer
            if consumer is None:
                try:
                    self.ensure_ready()
                except Exception as exc:
                    self._set_status(STATUS_DEGRADED, str(exc))
                    stop.wait(5.0)
                    continue
                consumer = self._consumer
                if consumer is None:
                    continue

            msg = consumer.poll(poll_interval_s)
            if msg is None:
                self._write_status()
                continue
            err = msg.error()
            if err is not None:
                if err.code() == KafkaError._PARTITION_EOF:
                    continue
                logger.warning(
                    "consumer poll error",
                    extra={"component": "consumer", "error": str(err)},
                )
                continue

            handled = self._process(msg)
            if handled:
                try:
                    consumer.commit(message=msg, asynchronous=False)
                except KafkaException as exc:
                    logger.warning(
                        "offset commit failed", extra={"component": "consumer", "error": str(exc)}
                    )

        self.close()

    def _process(self, msg: Message) -> bool:
        """Return True when the message is dealt with (safe to commit offset)."""
        raw = msg.value()
        try:
            envelope = parse_envelope(raw)
        except _NON_RETRYABLE as exc:
            return self._to_dlq(msg, exc, attempts=1)
        except Exception as exc:
            return self._to_dlq(msg, exc, attempts=1)

        try:
            outcome = self._apply_with_retries(envelope)
        except Exception as exc:  # retries exhausted -> DLQ
            return self._to_dlq(msg, exc, attempts=len(RETRY_BACKOFF_S))

        if outcome == DUPLICATE:
            self.duplicates += 1
            logger.info(
                "duplicate event ignored",
                extra={
                    "component": "consumer",
                    "event": "duplicate",
                    "eventId": str(envelope.event_id),
                },
            )
        else:
            self.processed += 1
            logger.info(
                "event applied",
                extra={
                    "component": "consumer",
                    "event": "applied",
                    "eventId": str(envelope.event_id),
                    "eventType": envelope.event_type.value,
                    "aggregateId": str(envelope.aggregate_id),
                    "version": envelope.aggregate_version,
                },
            )
        self._write_status()
        return True

    def _apply_with_retries(self, envelope: EventEnvelope) -> str:
        last: Exception | None = None
        for delay in RETRY_BACKOFF_S:
            try:
                return apply_envelope(envelope)
            except _NON_RETRYABLE:
                raise
            except Exception as exc:  # transient (DB down, deadlock, ...)
                last = exc
                logger.warning(
                    "event apply failed; retrying",
                    extra={"component": "consumer", "event": "retry", "error": str(exc)},
                )
                time.sleep(delay)
        assert last is not None
        raise last

    def _to_dlq(self, msg: Message, exc: Exception, attempts: int) -> bool:
        raw_headers = cast("list[tuple[str, str | bytes | None]]", msg.headers() or [])
        headers: list[tuple[str, str | bytes | None]] = list(raw_headers)
        headers += [
            (HEADER_DLQ_ERROR, str(exc).encode("utf-8")),
            (HEADER_DLQ_ATTEMPTS, str(attempts).encode("utf-8")),
            (HEADER_DLQ_SOURCE_TOPIC, (msg.topic() or "").encode("utf-8")),
            (HEADER_DLQ_SOURCE_PARTITION, str(msg.partition()).encode("utf-8")),
            (HEADER_DLQ_SOURCE_OFFSET, str(msg.offset()).encode("utf-8")),
            (HEADER_DLQ_FAILED_AT, str(time.time()).encode("utf-8")),
        ]
        producer = self._producer
        if producer is None:
            # No producer yet: leave the offset uncommitted so we retry later.
            logger.error(
                "cannot publish to DLQ: producer not ready", extra={"component": "consumer"}
            )
            return False

        try:
            producer.produce(
                TOPIC_JOBS_EVENTS_V1_DLQ,
                value=msg.value(),
                key=msg.key(),
                headers=headers,
            )
            remaining = producer.flush(self._operation_timeout_s)
        except (BufferError, KafkaException) as pub_exc:
            logger.error(
                "DLQ publish failed; offset not committed",
                extra={"component": "consumer", "error": str(pub_exc)},
            )
            return False

        if remaining != 0:
            logger.error(
                "DLQ publish timed out; offset not committed", extra={"component": "consumer"}
            )
            return False

        self.dlq_count += 1
        logger.warning(
            "message routed to DLQ",
            extra={
                "component": "consumer",
                "event": "dlq",
                "error": str(exc),
                "attempts": attempts,
                "sourceOffset": msg.offset(),
            },
        )
        self._write_status()
        return True


@lru_cache
def get_event_consumer() -> EventConsumer:
    from django.conf import settings

    return EventConsumer(
        settings.KAFKA_BOOTSTRAP_SERVERS,
        settings.KAFKA_CONSUMER_GROUP_ID,
        message_timeout_ms=settings.KAFKA_MESSAGE_TIMEOUT_MS,
    )
