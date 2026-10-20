"""Recruiter applicant APIs and dashboards (M7A)."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications import services as app_services
from apps.applications.models import Application, ApplicationStatus
from apps.candidates import services as candidate_services
from apps.candidates.models import Candidate
from apps.jobs.models import Job
from apps.jobs.services import upsert_job_from_snapshot
from contracts import EmploymentType, JobSnapshot
from contracts import JobStatus as ContractJobStatus

pytestmark = pytest.mark.django_db


def make_candidate(email: str = "cand@example.com", full_name: str = "Ada Lovelace") -> Candidate:
    return Candidate.objects.create_user(
        email=email,
        password="correct horse battery",
        full_name=full_name,
        headline="Backend engineer",
    )


def seed_job(recruiter_id: UUID, title: str = "Backend Engineer") -> Job:
    snapshot = JobSnapshot(
        id=uuid4(),
        recruiter_id=recruiter_id,
        title=title,
        description="Build services",
        company="Example",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        skills=["python"],
        status=ContractJobStatus.PUBLISHED,
        version=2,
        published_at=timezone.now(),
        closed_at=None,
        updated_at=timezone.now(),
    )
    upsert_job_from_snapshot(snapshot)
    return Job.objects.get(id=snapshot.id)


def recruiter_client(recruiter_id: UUID) -> APIClient:
    now = timezone.now()
    payload = {
        "sub": str(recruiter_id),
        "jti": str(uuid4()),
        "role": "recruiter",
        "iss": "job-service",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "token_type": "access",
    }
    token = jwt.encode(payload, settings.JOB_SERVICE_TEST_SIGNING_KEY, algorithm="ES256")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def candidate_client(candidate: Candidate) -> APIClient:
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {candidate_services.issue_access_token(candidate)}"
    )
    return client


def apply(candidate: Candidate, job: Job, status: str = ApplicationStatus.SUBMITTED) -> Application:
    application = app_services.apply_to_job(candidate, str(job.id), "Hello")
    if status != ApplicationStatus.SUBMITTED:
        Application.objects.filter(id=application.id).update(status=status)
        application.refresh_from_db()
    return application


def test_candidate_dashboard_counts_and_recent() -> None:
    candidate = make_candidate()
    other = make_candidate("other@example.com")
    job_a = seed_job(uuid4(), "Job A")
    job_b = seed_job(uuid4(), "Job B")
    apply(candidate, job_a, ApplicationStatus.SUBMITTED)
    apply(candidate, job_b, ApplicationStatus.SHORTLISTED)
    apply(other, job_a)

    response = candidate_client(candidate).get("/candidates/me/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["applications"]["total"] == 2
    assert body["applications"]["byStatus"]["SUBMITTED"] == 1
    assert body["applications"]["byStatus"]["SHORTLISTED"] == 1
    assert body["applications"]["byStatus"]["ACCEPTED"] == 0
    assert len(body["recent"]) == 2


def test_recruiter_dashboard_and_counts() -> None:
    recruiter_a = uuid4()
    recruiter_b = uuid4()
    candidate = make_candidate()
    job_a = seed_job(recruiter_a, "Role A")
    job_b = seed_job(recruiter_a, "Role B")
    job_c = seed_job(recruiter_a, "Role C")
    foreign_job = seed_job(recruiter_b, "Foreign")
    apply(candidate, job_a, ApplicationStatus.SUBMITTED)
    apply(candidate, job_b, ApplicationStatus.IN_REVIEW)
    apply(candidate, foreign_job, ApplicationStatus.ACCEPTED)

    client = recruiter_client(recruiter_a)
    dashboard = client.get("/recruiter/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["applications"]["total"] == 2
    assert body["applications"]["newCount"] == 1
    assert body["applications"]["byStatus"]["IN_REVIEW"] == 1
    assert body["applications"]["byStatus"]["ACCEPTED"] == 0
    assert len(body["recent"]) == 2

    counts = client.get("/recruiter/application-counts")
    assert counts.status_code == 200
    by_job = {row["jobId"]: row for row in counts.json()}
    assert by_job[str(job_a.id)]["total"] == 1
    assert by_job[str(job_b.id)]["byStatus"]["IN_REVIEW"] == 1
    assert by_job[str(job_c.id)]["total"] == 0
    assert str(foreign_job.id) not in by_job


def test_recruiter_list_and_detail_expose_applicant_profile() -> None:
    recruiter_id = uuid4()
    candidate = make_candidate()
    job = seed_job(recruiter_id)
    application = apply(candidate, job)

    client = recruiter_client(recruiter_id)
    listing = client.get(f"/recruiter/jobs/{job.id}/applications")
    assert listing.status_code == 200
    item = listing.json()["items"][0]
    assert item["candidate"]["full_name"] == "Ada Lovelace"
    assert item["candidate"]["email"] == candidate.email
    assert item["candidate"]["headline"] == "Backend engineer"
    assert item["candidate"]["has_resume"] is False
    assert item["candidate"]["resume_url"] == ""
    assert item["job"]["title"] == "Backend Engineer"

    detail = client.get(f"/recruiter/applications/{application.id}")
    assert detail.status_code == 200
    assert detail.json()["cover_letter"] == "Hello"


def test_foreign_application_detail_is_404() -> None:
    recruiter_a = uuid4()
    recruiter_b = uuid4()
    candidate = make_candidate()
    job = seed_job(recruiter_a)
    application = apply(candidate, job)

    response = recruiter_client(recruiter_b).get(f"/recruiter/applications/{application.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "APPLICATION_NOT_FOUND"


def test_status_change_updates_timestamp_and_is_owner_only() -> None:
    recruiter_a = uuid4()
    recruiter_b = uuid4()
    candidate = make_candidate()
    job = seed_job(recruiter_a)
    application = apply(candidate, job)
    before = application.status_updated_at

    owner = recruiter_client(recruiter_a)
    changed = owner.patch(
        f"/recruiter/applications/{application.id}/status",
        {"status": "SHORTLISTED"},
        format="json",
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "SHORTLISTED"
    application.refresh_from_db()
    assert application.status == ApplicationStatus.SHORTLISTED
    assert application.status_updated_at >= before

    blocked = owner.patch(
        f"/recruiter/applications/{application.id}/status",
        {"status": "SUBMITTED"},
        format="json",
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "VALIDATION_ERROR"

    foreign = recruiter_client(recruiter_b).patch(
        f"/recruiter/applications/{application.id}/status",
        {"status": "REJECTED"},
        format="json",
    )
    assert foreign.status_code == 404


def test_candidate_application_detail_includes_job() -> None:
    candidate = make_candidate()
    job = seed_job(uuid4(), "Data Engineer")
    application = apply(candidate, job)

    response = candidate_client(candidate).get(f"/candidates/me/applications/{application.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["title"] == "Data Engineer"
    assert body["job"]["company"] == job.company
