"""Liveness and readiness endpoints.

``/readyz`` checks the database and reports the consumer state without failing
readiness when Kafka is down (invariant I9).
"""

from __future__ import annotations

from django.conf import settings
from django.db import connection
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.events.models import ConsumerStatus
from config.env import get_settings

HEARTBEAT_STALE_SECONDS = 15


def _consumer_heartbeat() -> tuple[str, str]:
    """Return ``(consumer_state, kafka_state)`` from the consumer heartbeat row.

    The consumer runs in a separate process, so the only shared channel is the
    database. A missing or stale heartbeat means the consumer is not reporting.
    """
    row = ConsumerStatus.objects.filter(pk=1).first()
    if row is None or row.last_heartbeat_at is None:
        return "unknown", "unknown"
    age = (timezone.now() - row.last_heartbeat_at).total_seconds()
    if age > HEARTBEAT_STALE_SECONDS:
        return "stale", "unknown"
    return row.status, row.status


@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    description="Liveness probe. Always 200 while the process is up.",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def healthz(request: Request) -> Response:
    return Response({"status": "ok", "service": get_settings().service_name})


@extend_schema(
    responses={200: OpenApiTypes.OBJECT, 503: OpenApiTypes.OBJECT},
    description=(
        "Readiness probe. Fails only when the database is down. "
        "Kafka and the consumer are reported but never fail readiness."
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def readyz(request: Request) -> Response:
    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database_ok = False

    checks = {"database": "ok" if database_ok else "down"}
    if settings.KAFKA_CONSUMER_ENABLED:
        # Kafka is optional for availability, so consumer/kafka state is
        # reported, never fatal (invariant I9).
        consumer_state, kafka_state = _consumer_heartbeat()
        checks["consumer"] = consumer_state
        checks["kafka"] = kafka_state
    else:
        checks["consumer"] = "disabled"
        checks["kafka"] = "n/a"

    body = {"status": "ok" if database_ok else "unavailable", "checks": checks}
    http_status = status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(body, status=http_status)
