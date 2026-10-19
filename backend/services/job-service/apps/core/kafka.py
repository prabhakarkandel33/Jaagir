"""Kafka client for the Job Service (producer side).

Design constraints:

- **Kafka is optional for availability (invariant I9).** Nothing connects at
  import time. A background monitor retries the connection and topic creation
  and reports ``up``/``degraded``; the HTTP service and the relay keep working
  while Kafka is down.
- **Idempotent producer** (``enable.idempotence=True`` implies ``acks=all``),
  keyed per aggregate so each job's events stay ordered on one partition.
- ``publish`` blocks until the broker acks or the timeout expires, then raises
  ``KafkaUnavailableError`` so the relay can back off and retry.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from functools import lru_cache
from typing import Final

from confluent_kafka import KafkaError, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from contracts import TOPIC_JOBS_EVENTS_V1, TOPIC_JOBS_EVENTS_V1_DLQ

logger = logging.getLogger("apps.core.kafka")

STATUS_UNKNOWN: Final[str] = "unknown"
STATUS_UP: Final[str] = "up"
STATUS_DEGRADED: Final[str] = "degraded"

# 3 partitions on the main topic (keyed by jobId); a single DLQ partition.
TOPIC_SPECS: Final[tuple[NewTopic, ...]] = (
    NewTopic(TOPIC_JOBS_EVENTS_V1, num_partitions=3, replication_factor=1),
    NewTopic(TOPIC_JOBS_EVENTS_V1_DLQ, num_partitions=1, replication_factor=1),
)


class KafkaUnavailableError(RuntimeError):
    """Kafka could not accept or confirm the message. Retry later."""


class KafkaClient:
    def __init__(
        self,
        bootstrap_servers: str,
        *,
        message_timeout_ms: int = 5000,
        operation_timeout_s: float = 5.0,
    ) -> None:
        self._bootstrap = bootstrap_servers
        self._message_timeout_ms = message_timeout_ms
        self._operation_timeout_s = operation_timeout_s
        self._producer: Producer | None = None
        # Hold ONE AdminClient for the process lifetime. A temporary client is
        # garbage-collected before its create_topics futures resolve, which
        # fails with "_DESTROY: handle is terminating" and leaves topics
        # uncreated (then every produce fails with UNKNOWN_TOPIC_OR_PART).
        self._admin_client: AdminClient | None = None
        self._topics_ensured = False
        self._status = STATUS_UNKNOWN
        self._last_error: str | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

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
            "kafka status changed",
            extra={"component": "kafka", "event": "status", "status": status, "error": error},
        )

    # -- lifecycle --------------------------------------------------------
    def _build_producer(self) -> Producer:
        return Producer(
            {
                "bootstrap.servers": self._bootstrap,
                "acks": "all",
                "enable.idempotence": True,
                "message.timeout.ms": self._message_timeout_ms,
                "socket.timeout.ms": int(self._operation_timeout_s * 1000),
            }
        )

    def _admin(self) -> AdminClient:
        if self._admin_client is None:
            self._admin_client = AdminClient({"bootstrap.servers": self._bootstrap})
        return self._admin_client

    def _ensure_topics(self) -> None:
        futures = self._admin().create_topics(
            list(TOPIC_SPECS),
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
                extra={"component": "kafka", "event": "topic_ready", "topic": name},
            )

    def _ping(self) -> None:
        # Raises KafkaException when the broker is unreachable.
        self._admin().list_topics(timeout=self._operation_timeout_s)

    def ensure_ready(self) -> None:
        """Build the producer, create topics and confirm the broker. Raises."""
        with self._lock:
            if self._producer is None:
                self._producer = self._build_producer()
            if not self._topics_ensured:
                self._ensure_topics()
                self._topics_ensured = True
            self._ping()
        self._set_status(STATUS_UP, None)

    def start_monitor(self, interval_s: float = 10.0) -> None:
        """Start the background connect/retry loop (idempotent)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_s,),
            name="kafka-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop_monitor(self) -> None:
        self._stop.set()

    def _monitor_loop(self, interval_s: float) -> None:
        while not self._stop.is_set():
            try:
                self.ensure_ready()
            except Exception as exc:
                self._set_status(STATUS_DEGRADED, str(exc))
            self._stop.wait(interval_s)

    # -- produce ----------------------------------------------------------
    def publish(
        self,
        topic: str,
        value: bytes,
        key: str,
        headers: Sequence[tuple[str, bytes]],
    ) -> None:
        """Produce one message and wait for the broker ack.

        Raises ``KafkaUnavailableError`` when the message is not delivered in
        time, so the caller can leave the outbox row pending.
        """
        with self._lock:
            producer = self._producer
        if producer is None:
            raise KafkaUnavailableError("Kafka producer is not ready")

        delivery_error: dict[str, KafkaError] = {}

        def _on_delivery(err: KafkaError | None, _msg: object) -> None:
            if err is not None:
                delivery_error["error"] = err

        try:
            producer.produce(
                topic,
                value=value,
                key=key,
                headers=list(headers),
                on_delivery=_on_delivery,
            )
        except BufferError as exc:
            raise KafkaUnavailableError(f"producer queue full: {exc}") from exc
        except KafkaException as exc:
            raise KafkaUnavailableError(f"produce failed: {exc}") from exc

        remaining = producer.flush(self._operation_timeout_s)
        if delivery_error:
            raise KafkaUnavailableError(f"delivery failed: {delivery_error['error']}")
        if remaining != 0:
            raise KafkaUnavailableError(f"{remaining} message(s) not delivered before timeout")


@lru_cache
def get_kafka_client() -> KafkaClient:
    from django.conf import settings

    return KafkaClient(
        settings.KAFKA_BOOTSTRAP_SERVERS,
        message_timeout_ms=settings.KAFKA_MESSAGE_TIMEOUT_MS,
    )
