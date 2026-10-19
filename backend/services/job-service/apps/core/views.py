"""Liveness and readiness endpoints.

``/healthz`` is liveness only. ``/readyz`` checks the database and REPORTS the
Kafka status without ever failing readiness (invariant I9).
"""

from __future__ import annotations

from django.conf import settings
from django.db import connection
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.kafka import get_kafka_client
from config.env import get_settings


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
        "Kafka is reported but never fails readiness."
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

    kafka = get_kafka_client()
    if settings.KAFKA_MONITOR_ENABLED:
        # Lazily start the connect/retry monitor on the first probe. It never
        # blocks and never fails readiness (invariant I9).
        kafka.start_monitor()

    body = {
        "status": "ok" if database_ok else "unavailable",
        "checks": {
            "database": "ok" if database_ok else "down",
            # Kafka is optional for availability: reported, never fatal.
            "kafka": kafka.status,
        },
    }
    http_status = status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(body, status=http_status)
