"""Internal admin endpoints (token-guarded, invariant I8)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.internal import require_internal
from apps.outbox.models import OutboxEvent


class OutboxAdminView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT},
        description=(
            "Outbox visibility: pending count, age of the oldest pending row, "
            "the most recent error and how many events were published in the "
            "last hour. Requires X-Internal-Token."
        ),
    )
    def get(self, request: Request) -> Response:
        require_internal(request)

        pending_qs = OutboxEvent.objects.filter(published_at__isnull=True)
        oldest_created = (
            pending_qs.order_by("created_at").values_list("created_at", flat=True).first()
        )
        oldest_age = (timezone.now() - oldest_created).total_seconds() if oldest_created else 0.0
        last_error = (
            OutboxEvent.objects.exclude(last_error__isnull=True)
            .order_by("-id")
            .values_list("last_error", flat=True)
            .first()
        )
        published_last_hour = OutboxEvent.objects.filter(
            published_at__gte=timezone.now() - timedelta(hours=1)
        ).count()

        return Response(
            {
                "pending": pending_qs.count(),
                "oldestPendingAgeSeconds": round(oldest_age, 3),
                "lastError": last_error,
                "publishedLastHour": published_last_hour,
            }
        )
