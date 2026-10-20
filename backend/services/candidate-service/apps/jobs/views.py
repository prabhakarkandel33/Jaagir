"""Public job endpoints served from the local replica."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs import search
from apps.jobs.models import Job, JobStatus
from apps.jobs.serializers import (
    JobSearchParamsSerializer,
    JobSearchResultSerializer,
    JobSerializer,
)
from config.exceptions import ApiError


class JobSearchView(APIView):
    """GET /jobs -- search the local replica. Works while Kafka and the Job Service are down."""

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="jobs_search",
        parameters=[JobSearchParamsSerializer],
        responses={200: OpenApiResponse(description="{items, page, pageSize, total}")},
        description=(
            "Full-text search over the replicated published jobs. "
            "An empty `q` browses by recency. Filters: employmentType, location, skills."
        ),
    )
    def get(self, request: Request) -> Response:
        params = JobSearchParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data

        rows, total = search.search_jobs(
            q=data["q"],
            employment_type=data["employmentType"] or None,
            location=data["location"] or None,
            skills=data["skills"] or None,
            page=data["page"],
            page_size=data["pageSize"],
        )
        return Response(
            {
                "items": JobSearchResultSerializer(rows, many=True).data,
                "page": data["page"],
                "pageSize": data["pageSize"],
                "total": total,
            }
        )


class JobDetailView(APIView):
    """GET /jobs/:id -- published jobs only (drafts never reach the replica)."""

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="jobs_detail",
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
