"""Consumer / replica tests (invariant I3).

These cover the reliability paths that M4 is graded on: duplicate delivery,
out-of-order delivery, closed-job apply, and a poison message reaching the DLQ
without blocking the next message.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from apps.events.consumer import EventConsumer
from apps.events.models import ConsumerStatus, ProcessedEvent
from apps.events.services import APPLIED, DUPLICATE, apply_envelope
from apps.jobs.models import Job, JobStatus
from apps.jobs.services import upsert_job_from_snapshot
from contracts import (
    EmploymentType,
    EventEnvelope,
    JobEventType,
    JobSnapshot,
)
from contracts import (
    JobStatus as ContractJobStatus,
)

NOW = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

pytestmark = pytest.mark.django_db


def make_envelope(
    *,
    job_id: Any | None = None,
    version: int = 2,
    status: ContractJobStatus = ContractJobStatus.PUBLISHED,
    event_type: JobEventType = JobEventType.JOB_PUBLISHED,
) -> EventEnvelope:
    job_id = job_id or uuid4()
    published = NOW if status != ContractJobStatus.DRAFT else None
    closed = NOW if status == ContractJobStatus.CLOSED else None
    snapshot = JobSnapshot(
        id=job_id,
        recruiter_id=uuid4(),
        title="Backend Engineer",
        description="Build services",
        company="Example",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        skills=["python", "kafka"],
        status=status,
        version=version,
        published_at=published,
        closed_at=closed,
        updated_at=NOW,
    )
    return EventEnvelope(
        event_id=uuid4(),
        event_type=event_type,
        aggregate_id=job_id,
        aggregate_version=version,
        occurred_at=NOW,
        payload=snapshot,
    )


def test_same_event_twice_applies_once() -> None:
    envelope = make_envelope()
    assert apply_envelope(envelope) == APPLIED
    assert apply_envelope(envelope) == DUPLICATE

    assert Job.objects.count() == 1
    assert ProcessedEvent.objects.count() == 1


def test_out_of_order_older_version_is_ignored() -> None:
    job_id = uuid4()
    apply_envelope(make_envelope(job_id=job_id, version=3, event_type=JobEventType.JOB_UPDATED))
    apply_envelope(make_envelope(job_id=job_id, version=2, event_type=JobEventType.JOB_UPDATED))

    job = Job.objects.get(id=job_id)
    assert job.version == 3
    # Both events are recorded as processed even when the second is a no-op.
    assert ProcessedEvent.objects.count() == 2


def test_closed_event_updates_replica_status() -> None:
    job_id = uuid4()
    apply_envelope(make_envelope(job_id=job_id, version=2))
    apply_envelope(
        make_envelope(
            job_id=job_id,
            version=4,
            status=ContractJobStatus.CLOSED,
            event_type=JobEventType.JOB_CLOSED,
        )
    )
    job = Job.objects.get(id=job_id)
    assert job.status == JobStatus.CLOSED
    assert job.version == 4


class FakeProducer:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def produce(self, topic: str, value: bytes, key: bytes | None, headers: list) -> None:
        self.messages.append({"topic": topic, "value": value, "key": key, "headers": dict(headers)})

    def flush(self, timeout: float) -> int:
        return 0


class FakeMessage:
    def __init__(self, value: bytes) -> None:
        self._value = value

    def value(self) -> bytes:
        return self._value

    def key(self) -> bytes:
        return b"key"

    def topic(self) -> str:
        return "jobs.events.v1"

    def partition(self) -> int:
        return 0

    def offset(self) -> int:
        return 42

    def headers(self) -> list:
        return [("event-type", b"JobPublished")]


def test_poison_message_goes_to_dlq_and_next_message_processes() -> None:
    consumer = EventConsumer("localhost:9092", "test-group")
    producer = FakeProducer()
    consumer._producer = producer  # type: ignore[assignment]

    # 1. Malformed message -> DLQ, handled (offset safe to commit).
    assert consumer._process(FakeMessage(b"{not json")) is True  # type: ignore[arg-type]
    assert consumer.dlq_count == 1
    assert producer.messages[0]["topic"] == "jobs.events.v1.dlq"

    # 2. A healthy message after the poison one still applies.
    good = make_envelope()
    assert consumer._process(FakeMessage(good.to_json_bytes())) is True  # type: ignore[arg-type]
    assert consumer.processed == 1
    assert Job.objects.count() == 1


def test_transient_failure_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    consumer = EventConsumer("localhost:9092", "test-group")
    consumer._producer = FakeProducer()  # type: ignore[assignment]

    calls = {"n": 0}

    def flaky(envelope: EventEnvelope) -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("db hiccup")
        return APPLIED

    monkeypatch.setattr("apps.events.consumer.apply_envelope", flaky)
    monkeypatch.setattr("apps.events.consumer.time.sleep", lambda _s: None)

    assert consumer._process(FakeMessage(make_envelope().to_json_bytes())) is True  # type: ignore[arg-type]
    assert calls["n"] == 2
    assert consumer.processed == 1
    assert consumer.dlq_count == 0


def test_shared_upsert_is_used_by_paths() -> None:
    # upsert_job_from_snapshot is the single write path (consumer + M6 reconciler).
    snapshot = make_envelope(version=5).payload
    assert upsert_job_from_snapshot(snapshot) is True
    assert upsert_job_from_snapshot(snapshot) is False  # same version -> no change


def test_heartbeat_row_is_written_for_readyz() -> None:
    # /readyz runs in another process, so consumer state must reach the DB.
    consumer = EventConsumer("localhost:9092", "test-group")
    consumer._producer = FakeProducer()  # type: ignore[assignment]
    assert consumer._process(FakeMessage(make_envelope().to_json_bytes())) is True  # type: ignore[arg-type]

    row = ConsumerStatus.objects.get(pk=1)
    assert row.processed == 1
    assert row.dlq_count == 0
    assert row.last_heartbeat_at is not None
    assert row.status == consumer.status
