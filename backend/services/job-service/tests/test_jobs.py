"""Job command endpoints: state machine, ownership, outbox (M2 acceptance)."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.jobs.models import Job, JobStatus
from apps.outbox.models import OutboxEvent
from apps.recruiters.models import Recruiter
from apps.recruiters.services import issue_access_token

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"


def make_recruiter(email: str = "recruiter@example.com") -> Recruiter:
    return Recruiter.objects.create_user(email=email, password=PASSWORD, full_name="Ada Lovelace")


def auth_client(recruiter: Recruiter) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_access_token(recruiter)}")
    return client


def job_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Backend Engineer",
        "description": "Build reliable services.",
        "company": "Example Corp",
        "location": "Remote",
        "employment_type": "FULL_TIME",
        "skills": ["python", "postgres"],
    }
    payload.update(overrides)
    return payload


def create_job(client: APIClient, **overrides: object) -> dict[str, Any]:
    response = client.post("/recruiter/jobs", job_payload(**overrides), format="json")
    assert response.status_code == 201, response.json()
    return response.json()


def test_create_job_starts_draft_and_emits_nothing() -> None:
    client = auth_client(make_recruiter())
    body = create_job(client)

    assert body["status"] == JobStatus.DRAFT
    assert body["version"] == 1
    assert body["published_at"] is None
    assert OutboxEvent.objects.count() == 0


def test_create_requires_recruiter_role() -> None:
    assert APIClient().post("/recruiter/jobs", job_payload(), format="json").status_code == 401


def test_create_missing_fields_names_every_field() -> None:
    response = auth_client(make_recruiter()).post("/recruiter/jobs", {"skills": []}, format="json")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    for field in ("Title", "Description", "Company", "Location", "Employment type"):
        assert f"{field} is required." in error["message"]
    assert set(error["details"]) == {
        "title",
        "description",
        "company",
        "location",
        "employment_type",
    }


def test_publish_transitions_and_emits_event() -> None:
    client = auth_client(make_recruiter())
    job_id = create_job(client)["id"]

    response = client.post(f"/recruiter/jobs/{job_id}/publish")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == JobStatus.PUBLISHED
    assert body["version"] == 2
    assert body["published_at"] is not None

    event = OutboxEvent.objects.get()
    assert event.event_type == "JobPublished"
    assert str(event.aggregate_id) == job_id
    assert event.aggregate_version == 2
    assert event.payload["eventType"] == "JobPublished"
    assert event.payload["payload"]["status"] == "PUBLISHED"
    assert event.payload["payload"]["version"] == 2


def test_publish_twice_is_invalid_transition() -> None:
    client = auth_client(make_recruiter())
    job_id = create_job(client)["id"]
    client.post(f"/recruiter/jobs/{job_id}/publish")

    response = client.post(f"/recruiter/jobs/{job_id}/publish")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
    assert OutboxEvent.objects.count() == 1


def test_close_transitions_and_emits_event() -> None:
    client = auth_client(make_recruiter())
    job_id = create_job(client)["id"]
    client.post(f"/recruiter/jobs/{job_id}/publish")

    response = client.post(f"/recruiter/jobs/{job_id}/close")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == JobStatus.CLOSED
    assert body["version"] == 3
    assert body["closed_at"] is not None

    assert list(OutboxEvent.objects.order_by("id").values_list("event_type", flat=True)) == [
        "JobPublished",
        "JobClosed",
    ]


def test_close_draft_is_invalid_transition() -> None:
    client = auth_client(make_recruiter())
    job_id = create_job(client)["id"]

    response = client.post(f"/recruiter/jobs/{job_id}/close")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_draft_edit_bumps_version_without_event() -> None:
    client = auth_client(make_recruiter())
    created = create_job(client)

    response = client.put(
        f"/recruiter/jobs/{created['id']}", job_payload(title="Senior Engineer"), format="json"
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Senior Engineer"
    assert response.json()["version"] == 2
    assert OutboxEvent.objects.count() == 0


def test_published_edit_emits_updated_event() -> None:
    client = auth_client(make_recruiter())
    job_id = create_job(client)["id"]
    client.post(f"/recruiter/jobs/{job_id}/publish")

    response = client.put(
        f"/recruiter/jobs/{job_id}", job_payload(title="Updated Title"), format="json"
    )
    assert response.status_code == 200
    assert response.json()["version"] == 3

    event = OutboxEvent.objects.order_by("id").last()
    assert event is not None
    assert event.event_type == "JobUpdated"
    assert event.aggregate_version == 3
    assert event.payload["payload"]["title"] == "Updated Title"


def test_edit_closed_job_is_invalid_transition() -> None:
    client = auth_client(make_recruiter())
    job_id = create_job(client)["id"]
    client.post(f"/recruiter/jobs/{job_id}/publish")
    client.post(f"/recruiter/jobs/{job_id}/close")

    response = client.put(f"/recruiter/jobs/{job_id}", job_payload(), format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_other_recruiters_job_is_404() -> None:
    owner = auth_client(make_recruiter("owner@example.com"))
    intruder = auth_client(make_recruiter("intruder@example.com"))
    job_id = create_job(owner)["id"]

    assert intruder.get(f"/recruiter/jobs/{job_id}").status_code == 404
    assert intruder.post(f"/recruiter/jobs/{job_id}/publish").status_code == 404


def test_list_is_paginated_and_scoped_to_owner() -> None:
    owner = auth_client(make_recruiter("owner@example.com"))
    other = make_recruiter("other@example.com")
    for index in range(3):
        create_job(owner, title=f"Job {index}")
    Job.objects.create(
        recruiter=other,
        title="Not mine",
        description="x",
        company="y",
        location="z",
        employment_type="FULL_TIME",
    )

    response = owner.get("/recruiter/jobs")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["pageSize"] == 20
    assert len(body["items"]) == 3


def test_rollback_leaves_no_outbox_row_and_no_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = auth_client(make_recruiter())
    job_id = create_job(client)["id"]

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated failure after the state change")

    monkeypatch.setattr("apps.jobs.services.enqueue_job_event", boom)

    with pytest.raises(RuntimeError):
        client.post(f"/recruiter/jobs/{job_id}/publish")

    job = Job.objects.get(id=job_id)
    assert job.status == JobStatus.DRAFT
    assert job.version == 1
    assert OutboxEvent.objects.count() == 0


def test_public_detail_returns_published_only() -> None:
    client = auth_client(make_recruiter())
    job_id = create_job(client)["id"]

    assert APIClient().get(f"/jobs/{job_id}").status_code == 404  # draft hidden

    client.post(f"/recruiter/jobs/{job_id}/publish")
    published = APIClient().get(f"/jobs/{job_id}")
    assert published.status_code == 200
    assert published.json()["status"] == JobStatus.PUBLISHED

    client.post(f"/recruiter/jobs/{job_id}/close")
    assert APIClient().get(f"/jobs/{job_id}").status_code == 404  # closed hidden
