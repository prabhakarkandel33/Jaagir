"""Internal snapshot endpoints used by the Candidate reconciler (M6).

Both routes require ``X-Internal-Token`` (invariant I8) and are blocked at
Caddy in production. They expose NON-DRAFT jobs only: drafts never leave the
Job Service (ARCHITECTURE.md section 4.1).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.internal import require_internal
from apps.jobs.models import Job, JobStatus
from apps.jobs.snapshot import to_snapshot
from config.exceptions import ApiError

MAX_LIMIT = 1000


class SnapshotParamsSerializer(serializers.Serializer):
    """Keyset cursor (``after``), optional incremental window, page size."""

    after = serializers.UUIDField(required=False, allow_null=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=MAX_LIMIT, default=500)
    updatedAfter = serializers.DateTimeField(required=False, allow_null=True)


class InternalJobSnapshotView(APIView):
    """Page through every non-DRAFT job, ordered by id (keyset pagination)."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        parameters=[SnapshotParamsSerializer],
        responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT},
        description=(
            "Full job snapshots for status != DRAFT, keyset-paginated by id. "
            "Optional `updatedAfter` narrows the page to recently changed rows "
            "(incremental reconciliation). Requires X-Internal-Token."
        ),
    )
    def get(self, request: Request) -> Response:
        require_internal(request)
        params = SnapshotParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        after: UUID | None = params.validated_data.get("after")
        limit: int = params.validated_data["limit"]
        updated_after: datetime | None = params.validated_data.get("updatedAfter")

        qs = Job.objects.filter(
            status__in=[JobStatus.PUBLISHED, JobStatus.CLOSED],
        ).order_by("id")
        if after is not None:
            qs = qs.filter(id__gt=after)
        if updated_after is not None:
            qs = qs.filter(updated_at__gte=updated_after)

        rows = list(qs[: limit + 1])
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [to_snapshot(job).model_dump(mode="json", by_alias=True) for job in rows]
        next_after = str(rows[-1].id) if rows and has_more else None
        return Response({"items": items, "nextAfter": next_after, "hasMore": has_more})


class InternalJobDetailView(APIView):
    """One non-DRAFT snapshot by id (optional sync fallback for the peer)."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
        description="One non-DRAFT job snapshot by id. Requires X-Internal-Token.",
    )
    def get(self, request: Request, job_id: UUID) -> Response:
        require_internal(request)
        job = Job.objects.filter(
            id=job_id,
            status__in=[JobStatus.PUBLISHED, JobStatus.CLOSED],
        ).first()
        if job is None:
            raise ApiError(
                code="JOB_NOT_FOUND",
                message="Job not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        return Response(to_snapshot(job).model_dump(mode="json", by_alias=True))
