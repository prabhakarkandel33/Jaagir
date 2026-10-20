"""Application domain logic.

Applying enforces three facts without a check-then-insert race:

- the job exists in the local replica (else 404 ``JOB_NOT_FOUND``),
- the job is ``PUBLISHED`` (else 409 ``JOB_NOT_OPEN``),
- the candidate has not applied before -- enforced by the UNIQUE constraint and
  mapped from SQLSTATE 23505 to 409 ``APPLICATION_ALREADY_EXISTS`` (invariant I7).
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Count, QuerySet
from rest_framework import status

from apps.applications.models import Application, ApplicationStatus
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


def _owned_applications(recruiter_id: Any) -> QuerySet[Application]:
    return Application.objects.filter(job__recruiter_id=recruiter_id).select_related(
        "candidate",
        "job",
    )


def list_recruiter_applications(recruiter_id: Any) -> QuerySet[Application]:
    return _owned_applications(recruiter_id).order_by("-applied_at")


def get_recruiter_application(recruiter_id: Any, application_id: Any) -> Application:
    """Applicant detail. A foreign application is indistinguishable from 404."""
    application = _owned_applications(recruiter_id).filter(id=application_id).first()
    if application is None:
        raise _application_not_found()
    return application


def _application_not_found() -> ApiError:
    return ApiError(
        code="APPLICATION_NOT_FOUND",
        message="Application not found.",
        http_status=status.HTTP_404_NOT_FOUND,
    )


def update_application_status(
    recruiter_id: Any,
    application_id: Any,
    new_status: str,
) -> Application:
    """Recruiter moves an applicant through the post-submission statuses."""
    if new_status not in {
        ApplicationStatus.IN_REVIEW,
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.ACCEPTED,
    }:
        raise ApiError(
            code="INVALID_APPLICATION_STATUS",
            message="This status cannot be selected.",
            http_status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        application = (
            Application.objects.select_for_update()
            .filter(id=application_id, job__recruiter_id=recruiter_id)
            .first()
        )
        if application is None:
            raise _application_not_found()
        application.status = new_status
        application.save(update_fields=["status", "status_updated_at"])
    return application


def _status_breakdown(queryset: QuerySet[Application]) -> dict[str, Any]:
    counts = dict.fromkeys(ApplicationStatus.values, 0)
    rows = queryset.values("status").annotate(count=Count("id"))
    for row in rows:
        counts[row["status"]] = row["count"]
    return {"total": sum(counts.values()), "byStatus": counts}


def candidate_dashboard(candidate: Candidate) -> dict[str, Any]:
    queryset = Application.objects.filter(candidate=candidate)
    return {
        "applications": _status_breakdown(queryset),
        "recent": list(queryset.order_by("-applied_at")[:5]),
    }


def recruiter_dashboard(recruiter_id: Any) -> dict[str, Any]:
    queryset = _owned_applications(recruiter_id)
    breakdown = _status_breakdown(queryset)
    breakdown["newCount"] = breakdown["byStatus"][ApplicationStatus.SUBMITTED]
    return {
        "applications": breakdown,
        "recent": list(queryset.order_by("-applied_at")[:5]),
    }


def recruiter_application_counts(recruiter_id: Any) -> list[dict[str, Any]]:
    """Per-role applicant counts, one entry per owned role (zero included)."""
    rows = _owned_applications(recruiter_id).values("job_id", "status").annotate(count=Count("id"))
    by_job: dict[Any, dict[str, int]] = {}
    for row in rows:
        counts = by_job.setdefault(row["job_id"], dict.fromkeys(ApplicationStatus.values, 0))
        counts[row["status"]] = row["count"]

    results: list[dict[str, Any]] = []
    job_ids = Job.objects.filter(recruiter_id=recruiter_id).values_list("id", flat=True)
    for job_id in job_ids:
        counts = by_job.get(job_id, dict.fromkeys(ApplicationStatus.values, 0))
        results.append(
            {
                "jobId": job_id,
                "total": sum(counts.values()),
                "byStatus": counts,
            }
        )
    return results
