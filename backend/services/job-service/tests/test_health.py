"""Health endpoint tests (M1 acceptance)."""

from __future__ import annotations

import pytest
from django.test import Client


def test_healthz_ok() -> None:
    response = Client().get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "job-service"


def test_schema_is_served() -> None:
    response = Client().get("/schema")
    assert response.status_code == 200
    assert b"openapi" in response.content


def test_swagger_ui_is_served() -> None:
    response = Client().get("/docs")
    assert response.status_code == 200
    assert b"swagger" in response.content.lower()


@pytest.mark.django_db
def test_readyz_ok_with_database() -> None:
    response = Client().get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["database"] == "ok"
    # Kafka must never fail readiness (invariant I9).
    assert body["checks"]["kafka"] in {"unknown", "up", "degraded"}


@pytest.mark.django_db
def test_404_uses_uniform_error_shape() -> None:
    response = Client().get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
