"""Build and enqueue domain events (invariant I2).

Call these ONLY inside the same transaction as the job state change. The relay
(in M3) reads the rows and publishes them to Kafka.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from django.utils import timezone

from apps.jobs.snapshot import to_snapshot
from apps.outbox.models import OutboxEvent
from contracts import EventEnvelope

if TYPE_CHECKING:
    from apps.jobs.models import Job
    from contracts import JobEventType


def build_job_envelope(job: Job, event_type: JobEventType) -> EventEnvelope:
    """Wrap the FULL job snapshot in an envelope (ARCHITECTURE.md section 5)."""
    snapshot = to_snapshot(job)
    return EventEnvelope(
        event_id=uuid4(),
        event_type=event_type,
        aggregate_id=job.id,
        aggregate_version=job.version,
        occurred_at=timezone.now(),
        payload=snapshot,
    )


def enqueue_job_event(job: Job, event_type: JobEventType) -> OutboxEvent:
    """Insert the outbox row. Must run inside the caller's transaction."""
    envelope = build_job_envelope(job, event_type)
    return OutboxEvent.objects.create(
        event_id=envelope.event_id,
        aggregate_id=job.id,
        aggregate_version=job.version,
        event_type=event_type.value,
        payload=envelope.model_dump(mode="json", by_alias=True),
    )
