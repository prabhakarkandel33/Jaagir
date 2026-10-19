"""Transactional outbox (invariant I2).

Rows are written in the SAME transaction as the state change. Only the relay
publishes them to Kafka. See ARCHITECTURE.md section 6.1.
"""

from __future__ import annotations

from uuid import uuid4

from django.db import models
from django.utils import timezone


class OutboxEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    event_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    aggregate_id = models.UUIDField()
    aggregate_version = models.PositiveIntegerField()
    event_type = models.CharField(max_length=64)
    payload = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "outbox_events"
        indexes = [
            # The relay polls only unpublished rows, oldest first.
            models.Index(
                fields=["next_attempt_at", "id"],
                name="outbox_pending_idx",
                condition=models.Q(published_at__isnull=True),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} v{self.aggregate_version} ({self.aggregate_id})"
