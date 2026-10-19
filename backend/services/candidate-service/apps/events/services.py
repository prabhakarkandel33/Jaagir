"""Apply one event to the replica (invariant I3).

The inbox row and the replica change share ONE transaction: if the effect
fails, the ``processed_events`` row rolls back too, so a retry can re-apply.
A duplicate delivery inserts zero inbox rows and is skipped.
"""

from __future__ import annotations

from typing import Final

from django.db import connection, transaction

from apps.jobs.services import upsert_job_from_snapshot
from contracts import EventEnvelope

APPLIED: Final[str] = "applied"
DUPLICATE: Final[str] = "duplicate"

_INSERT_INBOX_SQL = """
INSERT INTO processed_events (event_id, event_type, processed_at)
VALUES (%s, %s, now())
ON CONFLICT (event_id) DO NOTHING
"""


def apply_envelope(envelope: EventEnvelope) -> str:
    """Record the event and apply its snapshot in one transaction.

    Returns ``APPLIED`` when this delivery did the work, ``DUPLICATE`` when the
    event id was already recorded (the effect is then skipped).
    """
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(_INSERT_INBOX_SQL, [envelope.event_id, envelope.event_type.value])
            first_delivery = cursor.rowcount == 1
        if not first_delivery:
            return DUPLICATE
        upsert_job_from_snapshot(envelope.payload)
    return APPLIED
