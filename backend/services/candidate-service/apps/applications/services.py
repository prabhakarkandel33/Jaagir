"""Application domain logic.

Applying enforces three facts without a check-then-insert race:

- the job exists in the local replica (else 404 ``JOB_NOT_FOUND``),
- the job is ``PUBLISHED`` (else 409 ``JOB_NOT_OPEN``),
- the candidate has not applied before -- enforced by the UNIQUE constraint and
  mapped from SQLSTATE 23505 to 409 ``APPLICATION_ALREADY_EXISTS`` (invariant I7).
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from rest_framework import status

from apps.applications.models import Application
from apps.candidates.models import Candidate
from apps.jobs.models import Job, JobStatus
from config.exceptions import ApiError

_UNIQUE_VIOLATION = "23505"


def _is_unique_violation(exc: IntegrityError) -> bool:
    cause = exc.__cause__ or exc.__context__
    return getattr(cause, "sqlstate", None) == _UNIQUE_VIOLATION


def apply_to_job(candidate: Candidate, job_id: str, cover_letter: str) -> Application:
    try:
        job = Job.objects.get(id=job_id)
    except (Job.DoesNotExist, ValueError):
        raise ApiError(
            code="JOB_NOT_FOUND",
            message="Job not found.",
            http_status=status.HTTP_404_NOT_FOUND,
        ) from None

    if job.status != JobStatus.PUBLISHED:
        raise ApiError(
            code="JOB_NOT_OPEN",
            message="This job is not open for applications.",
            http_status=status.HTTP_409_CONFLICT,
        )

    try:
        with transaction.atomic():
            return Application.objects.create(
                candidate=candidate,
                job=job,
                cover_letter=cover_letter,
                job_title_snapshot=job.title,
                company_snapshot=job.company,
            )
    except IntegrityError as exc:
        if _is_unique_violation(exc):
            raise ApiError(
                code="APPLICATION_ALREADY_EXISTS",
                message="You have already applied to this job.",
                http_status=status.HTTP_409_CONFLICT,
            ) from exc
        raise


def list_candidate_applications(candidate: Candidate):
    return Application.objects.filter(candidate=candidate).order_by("-applied_at")


def get_candidate_application(candidate: Candidate, application_id: str) -> Application:
    try:
        return Application.objects.get(id=application_id, candidate=candidate)
    except (Application.DoesNotExist, ValueError):
        raise ApiError(
            code="APPLICATION_NOT_FOUND",
            message="Application not found.",
            http_status=status.HTTP_404_NOT_FOUND,
        ) from None


def list_job_applications(recruiter_id: str, job_id: str):
    """Recruiter-facing list. Ownership comes from the replica's recruiter_id.

    A job that does not exist locally, or that belongs to another recruiter,
    looks identical (404) so a recruiter cannot probe other recruiters' jobs.
    """
    try:
        job = Job.objects.get(id=job_id, recruiter_id=recruiter_id)
    except (Job.DoesNotExist, ValueError):
        raise ApiError(
            code="JOB_NOT_FOUND",
            message="Job not found.",
            http_status=status.HTTP_404_NOT_FOUND,
        ) from None
    return Application.objects.filter(job=job).order_by("-applied_at")
