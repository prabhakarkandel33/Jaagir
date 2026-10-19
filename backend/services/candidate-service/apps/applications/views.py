"""Application endpoints: apply, candidate history, recruiter view."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications import services
from apps.applications.serializers import ApplicationSerializer, ApplySerializer
from apps.core.pagination import PageNumberPagination
from apps.core.permissions import IsCandidate, IsRecruiter


class ApplyView(APIView):
    permission_classes = [IsCandidate]

    @extend_schema(
        request=ApplySerializer,
        responses={
            201: ApplicationSerializer,
            404: OpenApiResponse(description="JOB_NOT_FOUND"),
            409: OpenApiResponse(description="JOB_NOT_OPEN or APPLICATION_ALREADY_EXISTS"),
        },
        description="Apply to a published job. One application per candidate per job.",
    )
    def post(self, request: Request, job_id: str) -> Response:
        serializer = ApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = services.apply_to_job(
            request.user,
            job_id,
            serializer.validated_data.get("cover_letter", ""),
        )
        return Response(
            ApplicationSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


class CandidateApplicationsView(APIView):
    permission_classes = [IsCandidate]

    @extend_schema(
        responses={200: ApplicationSerializer(many=True)},
        description="The candidate's applications, newest first.",
    )
    def get(self, request: Request) -> Response:
        queryset = services.list_candidate_applications(request.user)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ApplicationSerializer(page, many=True).data)


class CandidateApplicationDetailView(APIView):
    permission_classes = [IsCandidate]

    @extend_schema(
        responses={200: ApplicationSerializer, 404: OpenApiResponse(description="Not found.")},
        description="One of the candidate's applications.",
    )
    def get(self, request: Request, application_id: str) -> Response:
        application = services.get_candidate_application(request.user, application_id)
        return Response(ApplicationSerializer(application).data)


class RecruiterJobApplicationsView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={
            200: ApplicationSerializer(many=True),
            404: OpenApiResponse(description="Not found."),
        },
        description="Applications for one of the recruiter's jobs, newest first.",
    )
    def get(self, request: Request, job_id: str) -> Response:
        queryset = services.list_job_applications(request.user.id, job_id)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ApplicationSerializer(page, many=True).data)
