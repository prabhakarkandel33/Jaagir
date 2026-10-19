"""Public job endpoints served from the local replica."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.models import Job, JobStatus
from apps.jobs.serializers import JobSerializer
from config.exceptions import ApiError


class JobDetailView(APIView):
    """GET /jobs/:id -- published jobs only (drafts never reach the replica)."""

    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: JobSerializer, 404: OpenApiResponse(description="Not found.")},
        description="One published job from the local replica.",
    )
    def get(self, request: Request, job_id: str) -> Response:
        try:
            job = Job.objects.get(id=job_id, status=JobStatus.PUBLISHED)
        except (Job.DoesNotExist, ValueError):
            raise ApiError(
                code="JOB_NOT_FOUND",
                message="Job not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            ) from None
        return Response(JobSerializer(job).data)
