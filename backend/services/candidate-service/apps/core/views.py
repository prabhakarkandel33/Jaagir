"""Liveness and readiness endpoints.

``/readyz`` checks the database and reports the consumer state without failing
readiness when Kafka is down (invariant I9).
"""

from __future__ import annotations

from django.db import connection
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

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

    body = {
        "status": "ok" if database_ok else "unavailable",
        "checks": {
            "database": "ok" if database_ok else "down",
            # Consumer wiring lands in M4.
            "consumer": "unknown",
        },
    }
    http_status = status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(body, status=http_status)
