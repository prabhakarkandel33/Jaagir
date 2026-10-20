"""Recruiter dashboard totals (M7A)."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.recruiters.models import Recruiter
from apps.recruiters.services import issue_access_token

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"


def auth_client(recruiter: Recruiter) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_access_token(recruiter)}")
    return client


def create_job(client: APIClient, title: str) -> str:
    response = client.post(
        "/recruiter/jobs",
        {
            "title": title,
            "description": "Build reliable services.",
            "company": "Example Corp",
            "location": "Remote",
            "employment_type": "FULL_TIME",
            "skills": ["python"],
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    job_id: str = response.json()["id"]
    return job_id


def test_dashboard_reports_job_counts_and_recent_roles() -> None:
    recruiter = Recruiter.objects.create_user(
        email="dash@example.com", password=PASSWORD, full_name="Ada"
    )
    client = auth_client(recruiter)

    create_job(client, "Draft role")
    published = create_job(client, "Published role")
    closed = create_job(client, "Closed role")
    assert client.post(f"/recruiter/jobs/{published}/publish").status_code == 200
    assert client.post(f"/recruiter/jobs/{closed}/publish").status_code == 200
    assert client.post(f"/recruiter/jobs/{closed}/close").status_code == 200

    response = client.get("/recruiter/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["jobs"]["total"] == 3
    assert body["jobs"]["byStatus"] == {"DRAFT": 1, "PUBLISHED": 1, "CLOSED": 1}
    assert len(body["recentJobs"]) == 3


def test_dashboard_requires_recruiter_role() -> None:
    response = APIClient().get("/recruiter/dashboard")
    assert response.status_code == 401
