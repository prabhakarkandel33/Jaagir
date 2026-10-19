"""Internal admin endpoints: token guard and outbox visibility (invariant I8)."""

from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.jobs.services import create_job, publish_job
from apps.recruiters.models import Recruiter

pytestmark = pytest.mark.django_db

URL = "/internal/admin/outbox"
TOKEN = "test-internal-token"


def test_missing_token_is_rejected() -> None:
    response = APIClient().get(URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_wrong_token_is_rejected() -> None:
    response = APIClient().get(URL, HTTP_X_INTERNAL_TOKEN="nope")
    assert response.status_code == 401


def test_valid_token_returns_outbox_counters() -> None:
    response = APIClient().get(URL, HTTP_X_INTERNAL_TOKEN=TOKEN)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "pending",
        "oldestPendingAgeSeconds",
        "lastError",
        "publishedLastHour",
    }
    assert body["pending"] == 0
    assert body["oldestPendingAgeSeconds"] == 0.0


def test_pending_count_reflects_unpublished_rows() -> None:
    recruiter = Recruiter.objects.create_user(email="r@example.com", password="pw", full_name="A")
    for index in range(2):
        job = create_job(
            recruiter,
            {
                "title": f"Job {index}",
                "description": "x",
                "company": "y",
                "location": "Remote",
                "employment_type": "FULL_TIME",
                "skills": [],
            },
        )
        publish_job(recruiter, job.id)

    response = APIClient().get(URL, HTTP_X_INTERNAL_TOKEN=TOKEN)
    assert response.status_code == 200
    assert response.json()["pending"] == 2
    assert response.json()["oldestPendingAgeSeconds"] >= 0


@override_settings(INTERNAL_TOKEN="")
def test_empty_configured_token_rejects_everything() -> None:
    response = APIClient().get(URL, HTTP_X_INTERNAL_TOKEN="")
    assert response.status_code == 401
