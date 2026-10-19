"""Job command and query endpoints."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import PageNumberPagination
from apps.core.permissions import IsRecruiter
from apps.jobs import services
from apps.jobs.models import Job, JobStatus
from apps.jobs.serializers import JobSerializer, JobWriteSerializer
from config.exceptions import ApiError


class RecruiterJobListCreateView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={200: JobSerializer(many=True)},
        description="List the authenticated recruiter's jobs, newest first.",
    )
    def get(self, request: Request) -> Response:
        queryset = services.list_jobs_for_recruiter(request.user)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = JobSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=JobWriteSerializer,
        responses={201: JobSerializer},
        description="Create a job in DRAFT. No event is emitted for drafts.",
    )
    def post(self, request: Request) -> Response:
        serializer = JobWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = services.create_job(request.user, serializer.validated_data)
        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)


class RecruiterJobDetailView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={200: JobSerializer, 404: OpenApiResponse(description="Not found or not yours.")},
        description="Get one of the recruiter's jobs.",
    )
    def get(self, request: Request, job_id: Any) -> Response:
        job = services.get_owned_job(request.user, job_id)
        return Response(JobSerializer(job).data)

    @extend_schema(
        request=JobWriteSerializer,
        responses={
            200: JobSerializer,
            409: OpenApiResponse(description="Job is CLOSED."),
        },
        description="Edit a DRAFT or PUBLISHED job. Editing a published job emits JobUpdated.",
    )
    def put(self, request: Request, job_id: Any) -> Response:
        serializer = JobWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = services.update_job(request.user, job_id, serializer.validated_data)
        return Response(JobSerializer(job).data)


class JobPublishView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        request=None,
        responses={
            200: JobSerializer,
            409: OpenApiResponse(description="Only DRAFT jobs can be published."),
        },
        description="Publish a DRAFT job.",
    )
    def post(self, request: Request, job_id: Any) -> Response:
        job = services.publish_job(request.user, job_id)
        return Response(JobSerializer(job).data)


class JobCloseView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        request=None,
        responses={
            200: JobSerializer,
            409: OpenApiResponse(description="Only PUBLISHED jobs can be closed."),
        },
        description="Close a PUBLISHED job (terminal).",
    )
    def post(self, request: Request, job_id: Any) -> Response:
        job = services.close_job(request.user, job_id)
        return Response(JobSerializer(job).data)


class PublicJobDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: JobSerializer, 404: OpenApiResponse(description="No published job.")},
        description="Public view of a PUBLISHED job. Drafts and closed jobs are 404.",
    )
    def get(self, request: Request, job_id: Any) -> Response:
        job = Job.objects.filter(id=job_id, status=JobStatus.PUBLISHED).first()
        if job is None:
            raise ApiError(
                code="NOT_FOUND",
                message="Job not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        return Response(JobSerializer(job).data)
