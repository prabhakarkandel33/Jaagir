"""Job lifecycle commands.

The Job Service is the single writer of job truth. State machine:
``DRAFT -> PUBLISHED -> CLOSED`` (no unpublish; CLOSED is terminal).

Every command locks the row, bumps ``version``, and — for publish, update of a
published job, and close — writes the outbox row in the SAME transaction
(invariant I2, via ``with_tx``).
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count, QuerySet
from django.utils import timezone
from rest_framework import status

from apps.core.db import with_tx
from apps.jobs.models import Job, JobStatus
from apps.outbox.services import enqueue_job_event
from apps.recruiters.models import Recruiter
from config.exceptions import ApiError
from contracts import JobEventType


def _not_found() -> ApiError:
    # Same 404 whether the job is missing or owned by someone else: no probing.
    return ApiError(
        code="NOT_FOUND",
        message="Job not found.",
        http_status=status.HTTP_404_NOT_FOUND,
    )


def _invalid_transition(current: str, command: str) -> ApiError:
    return ApiError(
        code="INVALID_STATE_TRANSITION",
        message=f"Cannot {command} a job in status {current}.",
        http_status=status.HTTP_409_CONFLICT,
        details={"status": current, "command": command},
    )


def _locked_job(recruiter: Recruiter, job_id: Any) -> Job:
    job = Job.objects.select_for_update().filter(id=job_id, recruiter=recruiter).first()
    if job is None:
        raise _not_found()
    return job


def list_jobs_for_recruiter(recruiter: Recruiter) -> QuerySet[Job]:
    return Job.objects.filter(recruiter=recruiter).order_by("-created_at")


def recruiter_dashboard(recruiter: Recruiter) -> dict[str, Any]:
    """Job totals by status plus the five newest roles (single database, I1)."""
    queryset = Job.objects.filter(recruiter=recruiter)
    by_status = dict.fromkeys(JobStatus.values, 0)
    for row in queryset.values("status").annotate(count=Count("id")):
        by_status[row["status"]] = row["count"]
    return {
        "jobs": {"total": sum(by_status.values()), "byStatus": by_status},
        "recentJobs": list(queryset.order_by("-created_at")[:5]),
    }


def get_owned_job(recruiter: Recruiter, job_id: Any) -> Job:
    job = Job.objects.filter(id=job_id, recruiter=recruiter).first()
    if job is None:
        raise _not_found()
    return job


def create_job(recruiter: Recruiter, data: dict[str, Any]) -> Job:
    """Create a DRAFT. Emits no event (drafts are never replicated)."""

    def _do() -> Job:
        return Job.objects.create(
            recruiter=recruiter,
            status=JobStatus.DRAFT,
            version=1,
            **data,
        )

    return with_tx(_do)


def update_job(recruiter: Recruiter, job_id: Any, data: dict[str, Any]) -> Job:
    """Edit a DRAFT or PUBLISHED job. A published edit emits JobUpdated."""

    def _do() -> Job:
        job = _locked_job(recruiter, job_id)
        if job.status == JobStatus.CLOSED:
            raise _invalid_transition(job.status, "update")
        for field, value in data.items():
            setattr(job, field, value)
        job.version += 1
        job.save()
        if job.status == JobStatus.PUBLISHED:
            enqueue_job_event(job, JobEventType.JOB_UPDATED)
        return job

    return with_tx(_do)


def publish_job(recruiter: Recruiter, job_id: Any) -> Job:
    """DRAFT -> PUBLISHED. Bumps version and emits JobPublished."""

    def _do() -> Job:
        job = _locked_job(recruiter, job_id)
        if job.status != JobStatus.DRAFT:
            raise _invalid_transition(job.status, "publish")
        job.status = JobStatus.PUBLISHED
        job.published_at = timezone.now()
        job.version += 1
        job.save()
        enqueue_job_event(job, JobEventType.JOB_PUBLISHED)
        return job

    return with_tx(_do)


def close_job(recruiter: Recruiter, job_id: Any) -> Job:
    """PUBLISHED -> CLOSED (terminal). Bumps version and emits JobClosed."""

    def _do() -> Job:
        job = _locked_job(recruiter, job_id)
        if job.status != JobStatus.PUBLISHED:
            raise _invalid_transition(job.status, "close")
        job.status = JobStatus.CLOSED
        job.closed_at = timezone.now()
        job.version += 1
        job.save()
        enqueue_job_event(job, JobEventType.JOB_CLOSED)
        return job

    return with_tx(_do)
