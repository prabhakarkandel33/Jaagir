"""Health endpoint tests (M1 acceptance)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from apps.events.models import ConsumerStatus


def test_healthz_ok() -> None:
    response = Client().get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "candidate-service"


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
    # Consumer disabled in tests; readiness never fails on Kafka (invariant I9).
    assert body["checks"]["consumer"] == "disabled"
    assert body["checks"]["kafka"] == "n/a"


@pytest.mark.django_db
def test_404_uses_uniform_error_shape() -> None:
    response = Client().get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@override_settings(KAFKA_CONSUMER_ENABLED=True)
@pytest.mark.django_db
def test_readyz_reports_unknown_without_heartbeat() -> None:
    response = Client().get("/readyz")
    assert response.status_code == 200
    assert response.json()["checks"]["consumer"] == "unknown"
    assert response.json()["checks"]["kafka"] == "unknown"


@override_settings(KAFKA_CONSUMER_ENABLED=True)
@pytest.mark.django_db
def test_readyz_reports_fresh_heartbeat() -> None:
    ConsumerStatus.objects.create(pk=1, status="up", last_heartbeat_at=timezone.now())
    response = Client().get("/readyz")
    assert response.status_code == 200
    assert response.json()["checks"]["consumer"] == "up"
    assert response.json()["checks"]["kafka"] == "up"


@override_settings(KAFKA_CONSUMER_ENABLED=True)
@pytest.mark.django_db
def test_readyz_reports_stale_heartbeat() -> None:
    ConsumerStatus.objects.create(
        pk=1, status="up", last_heartbeat_at=timezone.now() - timedelta(seconds=60)
    )
    response = Client().get("/readyz")
    assert response.status_code == 200
    assert response.json()["checks"]["consumer"] == "stale"
    assert response.json()["checks"]["kafka"] == "unknown"
