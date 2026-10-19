"""Job replica domain logic.

``upsert_job_from_snapshot`` is the ONE function that writes a job from an
event snapshot; the consumer (M4) and the reconciler (M6) both use it, so both
paths share the same idempotency and version guards.
"""

from __future__ import annotations

from apps.jobs import repo
from apps.jobs.models import EmploymentType, Job, JobStatus
from contracts import JobSnapshot


def upsert_job_from_snapshot(snapshot: JobSnapshot) -> bool:
    """Build a replica row from a snapshot and version-guarded upsert it.

    Returns True when the replica changed, False when the snapshot was not
    newer than what we already have.
    """
    job = Job(
        id=snapshot.id,
        recruiter_id=snapshot.recruiter_id,
        title=snapshot.title,
        description=snapshot.description,
        company=snapshot.company,
        location=snapshot.location,
        employment_type=EmploymentType(snapshot.employment_type.value),
        skills=list(snapshot.skills),
        status=JobStatus(snapshot.status.value),
        version=snapshot.version,
        published_at=snapshot.published_at,
        closed_at=snapshot.closed_at,
        source_updated_at=snapshot.updated_at,
    )
    return repo.upsert_job(job)
