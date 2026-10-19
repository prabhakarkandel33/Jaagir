"""Inbox / dedup table (invariant I3).

Every processed event id lands here in the SAME transaction as its effect. A
duplicate delivery inserts zero rows (``ON CONFLICT DO NOTHING``) and is
skipped. See ARCHITECTURE.md section 6.2.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class ProcessedEvent(models.Model):
    event_id = models.UUIDField(primary_key=True, editable=False)
    event_type = models.CharField(max_length=64)
    processed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "processed_events"

    def __str__(self) -> str:
        return f"{self.event_id} ({self.event_type})"


class ConsumerStatus(models.Model):
    """Heartbeat for the consumer process, readable by the HTTP process.

    The consumer runs as its own process/container, so ``/readyz`` cannot read
    its in-memory state. The consumer upserts a single row here every poll; the
    web process reports ``up``/``degraded`` while the heartbeat is fresh, and
    ``stale`` when the consumer stops updating it.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    status = models.CharField(max_length=16, default="unknown")
    last_error = models.TextField(null=True, blank=True)
    processed = models.BigIntegerField(default=0)
    dlq_count = models.BigIntegerField(default=0)
    last_heartbeat_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "consumer_status"

    def __str__(self) -> str:
        return f"consumer={self.status} at {self.last_heartbeat_at}"
