"""Candidate-facing search over the replica (M5 acceptance).

The replica is populated directly here (the consumer is tested separately in
test_consumer.py); what matters is that search sees only PUBLISHED rows and
ranks them with the same SQL design as the Job Service.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.jobs.models import Job, JobStatus

pytestmark = pytest.mark.django_db


def make_job(
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
    if published_at is None and status in (JobStatus.PUBLISHED, JobStatus.CLOSED):
        published_at = datetime.now(UTC)
    return Job.objects.create(
        id=uuid4(),
        recruiter_id=uuid4(),
        title=title,
        description=description,
        company=company,
        location=location,
        employment_type=employment_type,
        skills=skills if skills is not None else ["python", "postgres"],
        status=status,
        version=1,
        published_at=published_at,
        source_updated_at=datetime.now(UTC),
    )


def search(client: APIClient, **params: Any) -> dict[str, Any]:
    response = client.get("/jobs", params)
    assert response.status_code == 200, response.content
    return response.json()


def test_only_published_replica_rows_are_searchable() -> None:
    make_job(title="Visible Rust Role")
    make_job(title="Draft Rust Role", status=JobStatus.DRAFT)
    make_job(title="Closed Rust Role", status=JobStatus.CLOSED)

    body = search(APIClient(), q="rust")

    assert body["total"] == 1
    assert [item["title"] for item in body["items"]] == ["Visible Rust Role"]


def test_title_match_outranks_description_match() -> None:
    make_job(title="Platform Engineer", description="Operate terraform modules daily.")
    make_job(title="Terraform Platform Engineer", description="Operate modules daily.")

    items = search(APIClient(), q="terraform")["items"]

    assert items[0]["title"] == "Terraform Platform Engineer"


def test_browse_is_newest_first() -> None:
    make_job(title="Older Replica Job", published_at=datetime(2026, 1, 1, tzinfo=UTC))
    make_job(title="Newer Replica Job", published_at=datetime(2026, 6, 1, tzinfo=UTC))

    body = search(APIClient())

    assert body["total"] == 2
    assert body["items"][0]["title"] == "Newer Replica Job"


def test_pagination_is_stable_and_non_overlapping() -> None:
    for index in range(5):
        make_job(title=f"Replica Engineer {index}")

    first = search(APIClient(), page=1, pageSize=2)
    second = search(APIClient(), page=2, pageSize=2)
    repeat = search(APIClient(), page=1, pageSize=2)

    assert first["total"] == 5
    ids_first = [item["id"] for item in first["items"]]
    ids_second = [item["id"] for item in second["items"]]
    assert ids_first == [item["id"] for item in repeat["items"]]
    assert set(ids_first).isdisjoint(ids_second)


def test_filters_restrict_results() -> None:
    make_job(title="Berlin Django", location="Berlin", skills=["django"])
    make_job(title="Paris Rails", location="Paris", skills=["rails"])
    make_job(title="Berlin Rails", location="Berlin", skills=["rails"], employment_type="CONTRACT")

    assert search(APIClient(), location="berlin")["total"] == 2
    assert search(APIClient(), skills=["rails"])["total"] == 2
    assert search(APIClient(), employmentType="CONTRACT")["total"] == 1
    assert search(APIClient(), location="Berlin", skills=["rails"])["total"] == 1


@pytest.mark.parametrize(
    "weird",
    ['"', "'", "&", ":*", "(", "\\", "a" * 10_000, "OR OR OR", "'; DROP TABLE jobs; --"],
)
def test_hostile_input_never_returns_500(weird: str) -> None:
    make_job()

    response = APIClient().get("/jobs", {"q": weird})

    assert response.status_code == 200


def test_search_works_with_no_kafka_and_no_job_service(monkeypatch: pytest.MonkeyPatch) -> None:
    # Search reads only the local replica; no outbound call may happen.
    make_job(title="Offline Capable Role")

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("search must not call the Job Service")

    monkeypatch.setattr("urllib.request.urlopen", explode)

    body = search(APIClient(), q="offline")

    assert body["total"] == 1
