"""Outbox relay tests: happy path, failure/backoff, ordering, at-least-once."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pytest
from django.utils import timezone

from apps.jobs.services import create_job, publish_job
from apps.outbox.models import OutboxEvent
from apps.outbox.relay import relay_once
from apps.recruiters.models import Recruiter
from contracts import TOPIC_JOBS_EVENTS_V1, parse_envelope

pytestmark = pytest.mark.django_db


class FakePublisher:
    """Records published messages; can be told to fail a number of times."""

    def __init__(self, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.sent: list[dict[str, Any]] = []

    def publish(
        self,
        topic: str,
        value: bytes,
        key: str,
        headers: Sequence[tuple[str, bytes]],
    ) -> None:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("kafka unavailable")
        self.sent.append(
            {
                "topic": topic,
                "envelope": json.loads(value),
                "key": key,
                "headers": dict(headers),
            }
        )


def make_recruiter(email: str = "recruiter@example.com") -> Recruiter:
    return Recruiter.objects.create_user(email=email, password="pw", full_name="Ada")


def make_published_job(title: str = "Backend Engineer") -> OutboxEvent:
    recruiter = make_recruiter(f"{title.replace(' ', '.')}@example.com".lower())
    job = create_job(
        recruiter,
        {
            "title": title,
            "description": "Build services.",
            "company": "Example",
            "location": "Remote",
            "employment_type": "FULL_TIME",
            "skills": ["python"],
        },
    )
    publish_job(recruiter, job.id)
    return OutboxEvent.objects.order_by("id").last()  # type: ignore[return-value]


def test_relay_publishes_pending_event_with_valid_envelope() -> None:
    row = make_published_job()
    publisher = FakePublisher()

    result = relay_once(publisher)

    assert result.locked is True
    assert result.published == 1
    assert result.failed == 0
    assert len(publisher.sent) == 1

    sent = publisher.sent[0]
    assert sent["topic"] == TOPIC_JOBS_EVENTS_V1
    assert sent["key"] == str(row.aggregate_id)
    assert sent["headers"]["event-type"] == b"JobPublished"
    envelope = parse_envelope(json.dumps(sent["envelope"]).encode())
    assert envelope.event_id == row.event_id
    assert envelope.aggregate_version == row.aggregate_version

    row.refresh_from_db()
    assert row.published_at is not None
    assert row.attempts == 0


def test_failure_keeps_row_pending_and_grows_attempts() -> None:
    row = make_published_job()
    before = timezone.now()

    result = relay_once(FakePublisher(fail_times=1))

    assert result.published == 0
    assert result.failed == 1
    assert result.error == "kafka unavailable"

    row.refresh_from_db()
    assert row.published_at is None
    assert row.attempts == 1
    assert row.last_error == "kafka unavailable"
    assert row.next_attempt_at > before


def test_batch_stops_on_first_failure_to_preserve_order() -> None:
    rows = [make_published_job(f"Job {i}") for i in range(3)]

    result = relay_once(FakePublisher(fail_times=1))

    assert result.published == 0
    assert result.failed == 1

    rows[0].refresh_from_db()
    rows[1].refresh_from_db()
    rows[2].refresh_from_db()
    assert rows[0].attempts == 1
    assert rows[1].attempts == 0 and rows[1].last_error is None
    assert rows[2].attempts == 0 and rows[2].last_error is None
    assert OutboxEvent.objects.filter(published_at__isnull=True).count() == 3


def test_backlog_drains_in_order_after_recovery() -> None:
    rows = [make_published_job(f"Job {i}") for i in range(3)]
    relay_once(FakePublisher(fail_times=1))  # first pass fails once
    OutboxEvent.objects.all().update(next_attempt_at=timezone.now())

    publisher = FakePublisher()
    result = relay_once(publisher)

    assert result.published == 3
    assert result.failed == 0
    sent_ids = [entry["envelope"]["eventId"] for entry in publisher.sent]
    assert sent_ids == [str(row.event_id) for row in rows]
    assert OutboxEvent.objects.filter(published_at__isnull=True).count() == 0


def test_crash_between_ack_and_mark_redelivers_same_event_id() -> None:
    row = make_published_job()
    first = FakePublisher()
    relay_once(first)

    # Simulate a crash after the broker ack but before published_at was saved.
    OutboxEvent.objects.filter(id=row.id).update(published_at=None, attempts=0)

    second = FakePublisher()
    relay_once(second)

    first_id = first.sent[0]["envelope"]["eventId"]
    second_id = second.sent[0]["envelope"]["eventId"]
    assert first_id == second_id == str(row.event_id)


def test_backoff_is_capped() -> None:
    from apps.outbox.relay import BACKOFF_CAP_SECONDS, backoff_seconds

    assert backoff_seconds(1) == 2
    assert backoff_seconds(3) == 8
    assert backoff_seconds(99) == BACKOFF_CAP_SECONDS
