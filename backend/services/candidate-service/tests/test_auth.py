"""Candidate auth tests plus cross-service (recruiter) token acceptance."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import jwt
import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.candidates.models import Candidate

pytestmark = pytest.mark.django_db


def test_register_returns_token_with_role() -> None:
    client = APIClient()
    response = client.post(
        "/auth/candidates/register",
        {"email": "New@Example.com", "password": "correct horse battery", "full_name": "Ada"},
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["candidate"]["email"] == "new@example.com"
    assert body["access"]
    # Token carries role=candidate.
    payload = jwt.decode(body["access"], options={"verify_signature": False})
    assert payload["role"] == "candidate"


def test_duplicate_register_is_409() -> None:
    Candidate.objects.create_user(email="dup@example.com", password="correct horse battery")
    client = APIClient()
    response = client.post(
        "/auth/candidates/register",
        {"email": "dup@example.com", "password": "correct horse battery", "full_name": "Ada"},
        format="json",
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_login_and_me_round_trip() -> None:
    Candidate.objects.create_user(email="me@example.com", password="correct horse battery")
    client = APIClient()

    login = client.post(
        "/auth/candidates/login",
        {"email": "me@example.com", "password": "correct horse battery"},
        format="json",
    )
    assert login.status_code == 200
    token = login.json()["access"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me = client.get("/candidates/me")
    assert me.status_code == 200
    assert me.json()["email"] == "me@example.com"


def test_refresh_returns_access_with_role_and_issuer() -> None:
    candidate = Candidate.objects.create_user(
        email="refresh@example.com", password="correct horse battery"
    )
    login = APIClient().post(
        "/auth/candidates/login",
        {"email": candidate.email, "password": "correct horse battery"},
        format="json",
    )
    assert login.status_code == 200
    assert login.json()["refresh"]

    response = APIClient().post(
        "/auth/candidates/refresh",
        {"refresh": login.json()["refresh"]},
        format="json",
    )

    assert response.status_code == 200
    payload = jwt.decode(response.json()["access"], options={"verify_signature": False})
    assert payload["role"] == "candidate"
    assert payload["iss"] == "candidate-service"
    assert response.json()["refresh"]


def test_refresh_rejects_a_job_service_token() -> None:
    now = timezone.now()
    payload = {
        "sub": str(uuid4()),
        "jti": str(uuid4()),
        "role": "candidate",
        "iss": "job-service",
        "iat": now,
        "exp": now + timedelta(days=7),
        "token_type": "refresh",
    }
    foreign = jwt.encode(payload, settings.JOB_SERVICE_TEST_SIGNING_KEY, algorithm="ES256")

    response = APIClient().post(
        "/auth/candidates/refresh",
        {"refresh": foreign},
        format="json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


def test_bad_login_is_401() -> None:
    Candidate.objects.create_user(email="bad@example.com", password="correct horse battery")
    client = APIClient()
    response = client.post(
        "/auth/candidates/login",
        {"email": "bad@example.com", "password": "wrong password"},
        format="json",
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def _recruiter_token() -> str:
    now = timezone.now()
    payload = {
        "sub": str(uuid4()),
        "jti": str(uuid4()),
        "role": "recruiter",
        "iss": "job-service",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "token_type": "access",
    }
    return jwt.encode(payload, settings.JOB_SERVICE_TEST_SIGNING_KEY, algorithm="ES256")


def test_recruiter_token_is_accepted_for_recruiter_route() -> None:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {_recruiter_token()}")
    # 404 (no such job for this recruiter) proves authentication+role passed;
    # a 401 would mean the recruiter JWT was rejected.
    response = client.get(f"/recruiter/jobs/{uuid4()}/applications")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_candidate_token_is_forbidden_on_recruiter_route() -> None:
    candidate = Candidate.objects.create_user(
        email="c@example.com", password="correct horse battery"
    )
    client = APIClient()
    login = client.post(
        "/auth/candidates/login",
        {"email": candidate.email, "password": "correct horse battery"},
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
    response = client.get(f"/recruiter/jobs/{uuid4()}/applications")
    assert response.status_code == 403
