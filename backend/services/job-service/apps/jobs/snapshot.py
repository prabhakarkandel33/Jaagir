"""Build the wire snapshot of a job (ARCHITECTURE.md section 5).

One function builds the snapshot for both the outbox envelope and the
reconciliation endpoint, so the two paths cannot drift.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from contracts import JobSnapshot
from contracts.events import EmploymentType
from contracts.events import JobStatus as ContractJobStatus

if TYPE_CHECKING:
    from apps.jobs.models import Job


def to_snapshot(job: Job) -> JobSnapshot:
    return JobSnapshot(
        id=job.id,
        recruiter_id=job.recruiter_id,
        title=job.title,
        description=job.description,
        company=job.company,
        location=job.location,
        employment_type=EmploymentType(job.employment_type),
        skills=list(job.skills or []),
        status=ContractJobStatus(job.status),
        version=job.version,
        published_at=job.published_at,
        closed_at=job.closed_at,
        updated_at=job.updated_at,
    )
