"""SQL for the job replica (ARCHITECTURE.md sections 6.2 and 6.3).

The version-guarded upsert is the single write path for the replica: the
consumer and (in M6) the reconciler both call ``upsert_job``. It is safe under
duplicate, out-of-order and lost-then-replayed delivery.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from django.db import connection

if TYPE_CHECKING:
    from apps.jobs.models import Job

# ``WHERE jobs.version < EXCLUDED.version`` is the order guard (invariant I3):
# an older event never overwrites a newer row.
UPSERT_JOB_SQL = """
INSERT INTO jobs (
    id, recruiter_id, title, description, company, location,
    employment_type, skills, status, version, published_at, closed_at,
    source_updated_at, synced_at
)
VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s,
    %s, now()
)
ON CONFLICT (id) DO UPDATE SET
    recruiter_id = EXCLUDED.recruiter_id,
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    company = EXCLUDED.company,
    location = EXCLUDED.location,
    employment_type = EXCLUDED.employment_type,
    skills = EXCLUDED.skills,
    status = EXCLUDED.status,
    version = EXCLUDED.version,
    published_at = EXCLUDED.published_at,
    closed_at = EXCLUDED.closed_at,
    source_updated_at = EXCLUDED.source_updated_at,
    synced_at = now()
WHERE jobs.version < EXCLUDED.version
"""


def _value(field: Any) -> Any:
    # Enum members (StrEnum) adapt as their string value.
    return getattr(field, "value", field)


def _params(job: Job) -> list[Any]:
    return [
        job.id,
        job.recruiter_id,
        job.title,
        job.description,
        job.company,
        job.location,
        _value(job.employment_type),
        list(job.skills or []),
        _value(job.status),
        job.version,
        job.published_at,
        job.closed_at,
        job.source_updated_at,
    ]


def upsert_job(job: Job) -> bool:
    """Insert or version-guarded update one replica row.

    Returns True when a row was inserted or updated, False when the incoming
    version was not newer (the event is then a harmless no-op).
    """
    with connection.cursor() as cursor:
        cursor.execute(UPSERT_JOB_SQL, _params(job))
        return cursor.rowcount == 1


def upsert_jobs(jobs: Iterable[Job]) -> int:
    """Upsert many rows in one transaction. Returns how many changed."""
    changed = 0
    with connection.cursor() as cursor:
        for job in jobs:
            cursor.execute(UPSERT_JOB_SQL, _params(job))
            changed += cursor.rowcount
    return changed
