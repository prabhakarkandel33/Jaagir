"""Application tests (invariant I7 and the M4 acceptance paths)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from django.db import connections

from apps.applications import services
from apps.applications.models import Application, ApplicationStatus
from apps.candidates.models import Candidate
from apps.jobs.models import Job
from apps.jobs.services import upsert_job_from_snapshot
from config.exceptions import ApiError
from contracts import (
    EmploymentType,
    JobSnapshot,
)
from contracts import (
    JobStatus as ContractJobStatus,
)

NOW = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)


def make_candidate(email: str = "cand@example.com") -> Candidate:
    return Candidate.objects.create_user(email=email, password="correct horse battery")


def seed_job(
    status: ContractJobStatus = ContractJobStatus.PUBLISHED, recruiter_id: UUID | None = None
) -> Job:
    snapshot = JobSnapshot(
        id=uuid4(),
        recruiter_id=recruiter_id or uuid4(),
        title="Backend Engineer",
        description="Build services",
        company="Example",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        skills=["python"],
        status=status,
        version=2,
        published_at=NOW,
        closed_at=NOW if status == ContractJobStatus.CLOSED else None,
        updated_at=NOW,
    )
    upsert_job_from_snapshot(snapshot)
    return Job.objects.get(id=snapshot.id)


@pytest.mark.django_db
def test_apply_creates_application_with_snapshot() -> None:
    candidate = make_candidate()
    job = seed_job()

    application = services.apply_to_job(candidate, str(job.id), "I am keen")

    assert application.status == ApplicationStatus.SUBMITTED
    assert application.job_title_snapshot == job.title
    assert application.company_snapshot == job.company
    assert Application.objects.filter(candidate=candidate).count() == 1


@pytest.mark.django_db
def test_duplicate_apply_maps_to_409() -> None:
    candidate = make_candidate()
    job = seed_job()
    services.apply_to_job(candidate, str(job.id), "")

    with pytest.raises(ApiError) as excinfo:
        services.apply_to_job(candidate, str(job.id), "")

    assert excinfo.value.status_code == 409
    assert excinfo.value.error_code == "APPLICATION_ALREADY_EXISTS"
    assert Application.objects.count() == 1


@pytest.mark.django_db
def test_apply_to_closed_job_is_409() -> None:
    candidate = make_candidate()
    job = seed_job(status=ContractJobStatus.CLOSED)

    with pytest.raises(ApiError) as excinfo:
        services.apply_to_job(candidate, str(job.id), "")

    assert excinfo.value.error_code == "JOB_NOT_OPEN"
    assert excinfo.value.status_code == 409


@pytest.mark.django_db
def test_apply_to_missing_job_is_404() -> None:
    candidate = make_candidate()

    with pytest.raises(ApiError) as excinfo:
        services.apply_to_job(candidate, str(uuid4()), "")

    assert excinfo.value.error_code == "JOB_NOT_FOUND"
    assert excinfo.value.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_ten_concurrent_applies_yield_one_row() -> None:
    candidate = make_candidate()
    job = seed_job()
    candidate_id = str(candidate.id)
    job_id = str(job.id)

    def worker(_n: int) -> str:
        try:
            local = Candidate.objects.get(id=candidate_id)
            services.apply_to_job(local, job_id, "")
            return "created"
        except ApiError as exc:
            return exc.error_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(worker, range(10)))

    assert results.count("created") == 1
    assert results.count("APPLICATION_ALREADY_EXISTS") == 9
    assert Application.objects.filter(job_id=job.id).count() == 1


@pytest.mark.django_db
def test_recruiter_cannot_read_another_recruiters_applications() -> None:
    candidate = make_candidate()
    recruiter_a = uuid4()
    recruiter_b = uuid4()
    job_a = seed_job(recruiter_id=recruiter_a)
    services.apply_to_job(candidate, str(job_a.id), "")

    # Owner sees the application.
    assert services.list_job_applications(str(recruiter_a), str(job_a.id)).count() == 1

    # A different recruiter gets a 404 (indistinguishable from "job missing").
    with pytest.raises(ApiError) as excinfo:
        services.list_job_applications(str(recruiter_b), str(job_a.id))
    assert excinfo.value.error_code == "JOB_NOT_FOUND"
