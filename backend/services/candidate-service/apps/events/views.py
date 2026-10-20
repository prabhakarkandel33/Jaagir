"""Internal reconciliation and DLQ endpoints (M6, invariant I8)."""

from __future__ import annotations

import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.internal import require_internal
from apps.events import reconciler
from apps.events.dlq import DEFAULT_LIMIT, replay_dlq
from apps.events.job_client import JobServiceUnavailable
from config.exceptions import ApiError

logger = logging.getLogger("apps.events.views")


class ReconcileParamsSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=reconciler.VALID_MODES, default=reconciler.MODE_FULL)


class DlqReplayParamsSerializer(serializers.Serializer):
    limit = serializers.IntegerField(
        required=False, default=DEFAULT_LIMIT, min_value=1, max_value=100_000
    )
    dryRun = serializers.BooleanField(required=False, default=False)


class ReconcileAdminView(APIView):
    """Run a reconciliation pass on demand (full or incremental)."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        request=None,
        parameters=[ReconcileParamsSerializer],
        responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT, 502: OpenApiTypes.OBJECT},
        description=(
            "Run a reconcile pass against the Job Service snapshot API and "
            "repair the replica. Writes one reconcile_runs row. "
            "Requires X-Internal-Token."
        ),
    )
    def post(self, request: Request) -> Response:
        require_internal(request)
        params = ReconcileParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        mode = params.validated_data["mode"]
        try:
            run = reconciler.reconcile(mode)
        except JobServiceUnavailable as exc:
            raise ApiError(
                code="JOB_SERVICE_UNAVAILABLE",
                message=f"Job Service snapshot API is not reachable: {exc}",
                http_status=status.HTTP_502_BAD_GATEWAY,
            ) from exc
        except Exception as exc:
            raise ApiError(
                code="RECONCILE_FAILED",
                message=str(exc),
                http_status=status.HTTP_502_BAD_GATEWAY,
            ) from exc
        return Response(
            {
                "mode": run.mode,
                "checked": run.checked,
                "repaired": run.repaired,
                "startedAt": run.started_at.isoformat(),
                "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
            }
        )


class SyncStatusView(APIView):
    """Replica freshness readout."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT},
        description=(
            "Last reconcile run, repaired count and local non-draft job count. "
            "Requires X-Internal-Token."
        ),
    )
    def get(self, request: Request) -> Response:
        require_internal(request)
        return Response(reconciler.sync_status())


class DlqReplayView(APIView):
    """Re-publish DLQ messages to the main topic (idempotent handler)."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        request=None,
        parameters=[DlqReplayParamsSerializer],
        responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT},
        description=(
            "Re-publish up to `limit` messages from jobs.events.v1.dlq to "
            "jobs.events.v1. `dryRun=true` only counts. Requires X-Internal-Token."
        ),
    )
    def post(self, request: Request) -> Response:
        require_internal(request)
        params = DlqReplayParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        result = replay_dlq(
            limit=params.validated_data["limit"],
            dry_run=params.validated_data["dryRun"],
        )
        return Response({"dryRun": params.validated_data["dryRun"], **result})
