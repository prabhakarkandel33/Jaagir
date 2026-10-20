"""Reconciliation: pull job state from the Job Service and repair the replica.

Why this exists (ARCHITECTURE.md section 6.3): Kafka delivery is what keeps the
replica fresh, but events can be lost (topic wiped, offsets reset, retention).
The reconciler compares the source of truth with the replica and repairs the
difference through the SAME upsert the consumer uses, so both paths share one
idempotency and version guard.

Rules:

- Missing or older local rows are upserted.
- A local row with a HIGHER version is an anomaly: log WARN, never downgrade.
- A local row absent from the source is an anomaly: log WARN, never delete.
- Every pass writes one ``reconcile_runs`` row, even when it fails.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any, Final
from uuid import UUID

from django.db import connection, transaction
from django.utils import timezone

from apps.events.job_client import fetch_snapshot_page
from apps.events.models import ReconcileRun
from apps.jobs.models import Job, JobStatus
from apps.jobs.services import upsert_job_from_snapshot
from config.env import get_settings
from contracts import JobSnapshot

logger = logging.getLogger("apps.events.reconciler")

MODE_FULL: Final[str] = "full"
MODE_INCREMENTAL: Final[str] = "incremental"
VALID_MODES: Final[tuple[str, ...]] = (MODE_FULL, MODE_INCREMENTAL)

# Incremental passes re-read a small overlap window so a job that changed just
# before the previous run cannot be missed (clock skew, in-flight transaction).
OVERLAP: Final[timedelta] = timedelta(minutes=10)

# How many "local row absent from the source" ids to log per pass.
ANOMALY_SAMPLE: Final[int] = 25

# Cap for a single pass, so a manual full reconcile cannot run forever.
DEFAULT_MAX_ROWS: Final[int] = 2_000_000

Client = Callable[..., dict[str, Any]]


def _incremental_since(mode: str) -> str | None:
    if mode != MODE_INCREMENTAL:
        return None
    previous = ReconcileRun.objects.exclude(started_at__isnull=True).order_by("-id").first()
    base = previous.started_at if previous is not None else timezone.now()
    return (base - OVERLAP).isoformat()


def _reset_seen_table() -> None:
    """Recreate the per-run set of source ids (temp table on this connection)."""
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS reconcile_seen")
        cursor.execute("CREATE TEMP TABLE reconcile_seen (id uuid PRIMARY KEY)")


def _log_local_only_rows() -> list[str]:
    """Find non-draft local rows that the full source sweep never mentioned.

    Never deletes them: an unexpected local row is a signal for a human, not a
    repair. Uses a temp table because a 100k ``IN (...)`` list exceeds the
    PostgreSQL parameter limit.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id FROM jobs
            WHERE status <> 'DRAFT'
              AND id NOT IN (SELECT id FROM reconcile_seen)
            ORDER BY id
            LIMIT %s
            """,
            [ANOMALY_SAMPLE + 1],
        )
        rows = [str(row[0]) for row in cursor.fetchall()]
    return rows[:ANOMALY_SAMPLE]


def reconcile(
    mode: str = MODE_FULL,
    *,
    client: Client = fetch_snapshot_page,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> ReconcileRun:
    """Run one pass. Always writes a ``reconcile_runs`` row."""
    if mode not in VALID_MODES:
        raise ValueError(f"unknown reconcile mode: {mode}")

    run = ReconcileRun.objects.create(mode=mode, started_at=timezone.now())
    checked = 0
    repaired = 0
    stale_local = 0
    try:
        updated_after = _incremental_since(mode)
        after: str | None = None
        if mode == MODE_FULL:
            _reset_seen_table()
        # Fetch pages OUTSIDE a transaction (network I/O must not hold locks),
        # then apply each page in its own short transaction.
        while checked < max_rows:
            page = client(
                after=after,
                limit=get_settings().reconcile_batch_limit,
                updated_after=updated_after,
            )
            items = page.get("items", [])
            if not items:
                break
            with transaction.atomic():
                for raw in items:
                    snapshot = JobSnapshot.model_validate(raw)
                    changed = upsert_job_from_snapshot(snapshot)
                    checked += 1
                    if changed:
                        repaired += 1
                    else:
                        stale_local += _is_local_newer(snapshot)
                if mode == MODE_FULL:
                    _remember(items)
            after = page.get("nextAfter")
            if not after:
                break

        if mode == MODE_FULL:
            sample = _log_local_only_rows()
            if sample:
                logger.warning(
                    "replica rows missing from the source (not deleted)",
                    extra={
                        "component": "reconciler",
                        "event": "local_only_rows",
                        "sample": sample,
                    },
                )
    except Exception as exc:
        run.finished_at = timezone.now()
        run.checked = checked
        run.repaired = repaired
        run.error = str(exc)
        run.save(update_fields=["finished_at", "checked", "repaired", "error"])
        logger.warning(
            "reconcile failed",
            extra={"component": "reconciler", "event": "failed", "mode": mode, "error": str(exc)},
        )
        raise

    run.finished_at = timezone.now()
    run.checked = checked
    run.repaired = repaired
    run.save(update_fields=["finished_at", "checked", "repaired"])
    logger.info(
        "reconcile finished",
        extra={
            "component": "reconciler",
            "event": "finished",
            "mode": mode,
            "checked": checked,
            "repaired": repaired,
            "localNewer": stale_local,
        },
    )
    return run


def _remember(items: list[dict[str, Any]]) -> None:
    rows = [(UUID(str(item["id"])),) for item in items]
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO reconcile_seen (id) VALUES (%s) ON CONFLICT DO NOTHING", rows
        )


def _is_local_newer(snapshot: JobSnapshot) -> int:
    """1 when the replica is ahead of the source (anomaly), else 0."""
    local_version = Job.objects.filter(id=snapshot.id).values_list("version", flat=True).first()
    if local_version is not None and local_version > snapshot.version:
        logger.warning(
            "replica version is ahead of the source; left untouched",
            extra={
                "component": "reconciler",
                "event": "local_newer",
                "jobId": str(snapshot.id),
                "localVersion": local_version,
                "sourceVersion": snapshot.version,
            },
        )
        return 1
    return 0


def sync_status() -> dict[str, Any]:
    """Summary for ``GET /internal/admin/sync-status``."""
    last = ReconcileRun.objects.first()
    return {
        "lastRun": None
        if last is None
        else {
            "id": last.id,
            "mode": last.mode,
            "startedAt": last.started_at.isoformat(),
            "finishedAt": last.finished_at.isoformat() if last.finished_at else None,
            "checked": last.checked,
            "repaired": last.repaired,
            "error": last.error,
        },
        "lastRepaired": last.repaired if last is not None else 0,
        "localJobCount": Job.objects.exclude(status=JobStatus.DRAFT).count(),
    }
