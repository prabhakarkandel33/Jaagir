"""Internal reconciliation snapshot endpoint (M6).

Covers the contract the Candidate reconciler depends on: token guard, drafts
excluded, keyset paging without gaps or repeats, the incremental window, and
full payloads.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.jobs.models import Job, JobStatus
from apps.jobs.services import close_job, create_job, publish_job, update_job
from apps.recruiters.models import Recruiter

pytestmark = pytest.mark.django_db

URL = "/internal/jobs/snapshot"
TOKEN = "test-internal-token"
HEADERS = {"HTTP_X_INTERNAL_TOKEN": TOKEN}


def _recruiter(email: str = "r@example.com") -> Recruiter:
    return Recruiter.objects.create_user(
        email=email, password="pw", full_name="A", company_name="Acme"
    )


def _published_job(recruiter: Recruiter, title: str = "Backend Engineer") -> Job:
    job = create_job(
        recruiter=recruiter,
        data={
            "title": title,
            "description": "Build services",
            "company": "Acme",
            "location": "Berlin",
            "employment_type": "FULL_TIME",
            "skills": ["python", "django"],
        },
    )
    return publish_job(recruiter=recruiter, job_id=job.id)


def test_snapshot_requires_internal_token() -> None:
    response = APIClient().get(URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_snapshot_excludes_drafts() -> None:
    recruiter = _recruiter()
    create_job(
        recruiter=recruiter,
        data={
            "title": "Draft only",
            "description": "x",
            "company": "Acme",
            "location": "Berlin",
            "employment_type": "FULL_TIME",
            "skills": [],
        },
    )
    response = APIClient().get(URL, **HEADERS)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_snapshot_returns_full_payload() -> None:
    recruiter = _recruiter()
    job = _published_job(recruiter)
    response = APIClient().get(URL, **HEADERS)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item) == {
        "id",
        "recruiterId",
        "title",
        "description",
        "company",
        "location",
        "employmentType",
        "skills",
        "status",
        "version",
        "publishedAt",
        "closedAt",
        "updatedAt",
    }
    assert item["id"] == str(job.id)
    assert item["status"] == "PUBLISHED"
    assert item["version"] == job.version
    assert item["skills"] == ["python", "django"]


def test_keyset_paging_has_no_gaps_or_repeats() -> None:
    recruiter = _recruiter()
    created = [_published_job(recruiter, title=f"Engineer {index}") for index in range(5)]

    seen: list[str] = []
    after: str | None = None
    for _ in range(10):
        params: dict[str, str] = {"limit": "2"}
        if after is not None:
            params["after"] = after
        body = APIClient().get(URL, params, **HEADERS).json()
        seen.extend(item["id"] for item in body["items"])
        after = body["nextAfter"]
        if not body["hasMore"]:
            break

    assert len(seen) == len(set(seen)) == 5
    assert set(seen) == {str(job.id) for job in created}


def test_limit_is_capped_and_validated() -> None:
    response = APIClient().get(URL, {"limit": "1001"}, **HEADERS)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_updated_after_narrows_the_page() -> None:
    recruiter = _recruiter()
    old = _published_job(recruiter, title="Old job")
    fresh = _published_job(recruiter, title="Fresh job")

    Job.objects.filter(id=old.id).update(updated_at=timezone.now() - timedelta(days=2))
    cutoff = timezone.now() - timedelta(hours=1)

    body = APIClient().get(URL, {"updatedAfter": cutoff.isoformat()}, **HEADERS).json()
    ids = {item["id"] for item in body["items"]}
    assert str(fresh.id) in ids
    assert str(old.id) not in ids


def test_closed_jobs_are_included_with_terminal_state() -> None:
    recruiter = _recruiter()
    job = _published_job(recruiter)
    close_job(recruiter=recruiter, job_id=job.id)

    items = APIClient().get(URL, **HEADERS).json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == JobStatus.CLOSED.value
    assert items[0]["closedAt"] is not None


def test_internal_detail_returns_one_non_draft_job() -> None:
    recruiter = _recruiter()
    job = _published_job(recruiter)

    response = APIClient().get(f"/internal/jobs/{job.id}", **HEADERS)
    assert response.status_code == 200
    assert response.json()["id"] == str(job.id)

    draft = create_job(
        recruiter=recruiter,
        data={
            "title": "Draft",
            "description": "x",
            "company": "Acme",
            "location": "Berlin",
            "employment_type": "FULL_TIME",
            "skills": [],
        },
    )
    hidden = APIClient().get(f"/internal/jobs/{draft.id}", **HEADERS)
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_snapshot_version_tracks_updates() -> None:
    recruiter = _recruiter()
    job = _published_job(recruiter)
    updated = update_job(recruiter=recruiter, job_id=job.id, data={"title": "Renamed"})

    item = APIClient().get(URL, **HEADERS).json()["items"][0]
    assert item["version"] == updated.version
    assert item["title"] == "Renamed"


@pytest.mark.parametrize("value", ["not-a-uuid", "123"])
def test_bad_cursor_is_rejected(value: str) -> None:
    response = APIClient().get(URL, {"after": value}, **HEADERS)
    assert response.status_code == 400
