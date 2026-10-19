"""Public job search: FTS ranking, filters, paging, hostile input (M5 acceptance).

These run against the real PostgreSQL search path (trigger + tsvector +
``websearch_to_tsquery``), not a mock, so they also prove the migration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.jobs.models import Job, JobStatus
from apps.recruiters.models import Recruiter

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"


def make_recruiter(email: str = "search@example.com") -> Recruiter:
    return Recruiter.objects.create_user(email=email, password=PASSWORD, full_name="Searcher")


def make_job(
    recruiter: Recruiter,
    *,
    status: str = JobStatus.PUBLISHED,
    title: str = "Backend Engineer",
    description: str = "Build reliable services.",
    company: str = "Example Corp",
    location: str = "Remote",
    employment_type: str = "FULL_TIME",
    skills: list[str] | None = None,
    published_at: datetime | None = None,
) -> Job:
    # The real publish command always stamps published_at; mirror that here so
    # the browse ordering is meaningful.
    if published_at is None and status in (JobStatus.PUBLISHED, JobStatus.CLOSED):
        published_at = datetime.now(UTC)
    return Job.objects.create(
        recruiter=recruiter,
        title=title,
        description=description,
        company=company,
        location=location,
        employment_type=employment_type,
        skills=skills if skills is not None else ["python", "postgres"],
        status=status,
        published_at=published_at,
    )


def search(client: APIClient, **params: Any) -> dict[str, Any]:
    response = client.get("/jobs", params)
    assert response.status_code == 200, response.content
    return response.json()


def test_only_published_jobs_are_searchable() -> None:
    recruiter = make_recruiter()
    make_job(recruiter, title="Visible Kubernetes Role", status=JobStatus.PUBLISHED)
    make_job(recruiter, title="Hidden Kubernetes Draft", status=JobStatus.DRAFT)
    make_job(recruiter, title="Hidden Kubernetes Closed", status=JobStatus.CLOSED)

    body = search(APIClient(), q="kubernetes")

    assert body["total"] == 1
    assert [item["title"] for item in body["items"]] == ["Visible Kubernetes Role"]


def test_title_match_outranks_description_match() -> None:
    recruiter = make_recruiter()
    # `kubernetes` in the description only.
    make_job(
        recruiter,
        title="Platform Engineer",
        description="You will operate kubernetes clusters every day.",
    )
    # `kubernetes` in the title (weight A beats weight C).
    make_job(
        recruiter,
        title="Kubernetes Platform Engineer",
        description="Operate clusters every day.",
    )

    items = search(APIClient(), q="kubernetes")["items"]

    assert items[0]["title"] == "Kubernetes Platform Engineer"


def test_empty_query_browses_newest_first() -> None:
    recruiter = make_recruiter()
    make_job(recruiter, title="Older Job", published_at=datetime(2026, 1, 1, tzinfo=UTC))
    make_job(recruiter, title="Newest Job", published_at=datetime(2026, 6, 1, tzinfo=UTC))

    body = search(APIClient())

    assert body["total"] == 2
    assert body["items"][0]["title"] == "Newest Job"


def test_pagination_is_stable_and_non_overlapping() -> None:
    recruiter = make_recruiter()
    for index in range(5):
        make_job(recruiter, title=f"Engineer {index}")

    first = search(APIClient(), page=1, pageSize=2)
    second = search(APIClient(), page=2, pageSize=2)
    repeat = search(APIClient(), page=1, pageSize=2)

    assert first["total"] == second["total"] == 5
    assert len(first["items"]) == len(second["items"]) == 2
    ids_first = [item["id"] for item in first["items"]]
    ids_second = [item["id"] for item in second["items"]]
    assert ids_first == [item["id"] for item in repeat["items"]]
    assert set(ids_first).isdisjoint(ids_second)


def test_filters_restrict_results() -> None:
    recruiter = make_recruiter()
    make_job(recruiter, title="Berlin Django", location="Berlin", skills=["django"])
    make_job(recruiter, title="Paris Rails", location="Paris", skills=["rails"])
    make_job(
        recruiter,
        title="Berlin Rails",
        location="Berlin",
        skills=["rails"],
        employment_type="CONTRACT",
    )

    assert search(APIClient(), location="berlin")["total"] == 2
    assert search(APIClient(), skills=["rails"])["total"] == 2
    assert search(APIClient(), employmentType="CONTRACT")["total"] == 1
    assert search(APIClient(), location="Berlin", skills=["rails"])["total"] == 1


def test_page_beyond_the_end_returns_empty_page_not_error() -> None:
    recruiter = make_recruiter()
    make_job(recruiter)

    body = search(APIClient(), page=99, pageSize=10)

    assert body["items"] == []
    assert body["total"] == 1


@pytest.mark.parametrize(
    "weird",
    [
        '"',
        "'",
        "&",
        ":*",
        "!",
        "(",
        "\\",
        "a" * 10_000,
        "  ",
        "OR OR OR",
        "'; DROP TABLE jobs; --",
        "%(limit)s",
    ],
)
def test_hostile_input_never_returns_500(weird: str) -> None:
    recruiter = make_recruiter()
    make_job(recruiter)

    response = APIClient().get("/jobs", {"q": weird})

    assert response.status_code == 200


def test_sql_injection_attempt_does_not_drop_the_table() -> None:
    recruiter = make_recruiter()
    make_job(recruiter)

    search(APIClient(), q="'; DROP TABLE jobs; --")

    assert Job.objects.count() == 1


def test_invalid_filter_value_is_rejected_not_ignored() -> None:
    response = APIClient().get("/jobs", {"employmentType": "NOT_A_TYPE"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] in {"VALIDATION_ERROR", "INVALID_REQUEST"}
