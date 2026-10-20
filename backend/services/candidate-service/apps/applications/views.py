"""Application endpoints: apply, candidate history, recruiter view."""

from __future__ import annotations

from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications import services
from apps.applications.serializers import (
    ApplicationSerializer,
    ApplicationStatusSerializer,
    ApplySerializer,
    CandidateApplicationDetailSerializer,
    CandidateDashboardSerializer,
    JobApplicationCountSerializer,
    RecruiterApplicationSerializer,
    RecruiterDashboardSerializer,
)
from apps.candidates import resume
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
        return Response(CandidateApplicationDetailSerializer(application).data)


class CandidateDashboardView(APIView):
    permission_classes = [IsCandidate]

    @extend_schema(
        responses={200: CandidateDashboardSerializer},
        description="Application totals by status plus the five most recent.",
    )
    def get(self, request: Request) -> Response:
        data = services.candidate_dashboard(request.user)
        return Response(CandidateDashboardSerializer(data).data)


class RecruiterJobApplicationsView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={
            200: RecruiterApplicationSerializer(many=True),
            404: OpenApiResponse(description="Not found."),
        },
        description="Applications for one of the recruiter's jobs, newest first.",
    )
    def get(self, request: Request, job_id: str) -> Response:
        queryset = services.list_job_applications(request.user.id, job_id).select_related(
            "candidate",
            "job",
        )
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            RecruiterApplicationSerializer(page, many=True).data
        )


class RecruiterApplicationListView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={200: RecruiterApplicationSerializer(many=True)},
        description="All applicants across the recruiter's roles, newest first.",
    )
    def get(self, request: Request) -> Response:
        queryset = services.list_recruiter_applications(request.user.id)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            RecruiterApplicationSerializer(page, many=True).data
        )


class RecruiterApplicationDetailView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={
            200: RecruiterApplicationSerializer,
            404: OpenApiResponse(description="APPLICATION_NOT_FOUND"),
        },
        description="Applicant profile, cover letter and job for one application.",
    )
    def get(self, request: Request, application_id: str) -> Response:
        application = services.get_recruiter_application(request.user.id, application_id)
        return Response(RecruiterApplicationSerializer(application).data)


class RecruiterApplicationStatusView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        request=ApplicationStatusSerializer,
        responses={
            200: RecruiterApplicationSerializer,
            400: OpenApiResponse(description="Invalid status."),
            404: OpenApiResponse(description="APPLICATION_NOT_FOUND"),
        },
        description="Move an applicant to IN_REVIEW, SHORTLISTED, REJECTED or ACCEPTED.",
    )
    def patch(self, request: Request, application_id: str) -> Response:
        serializer = ApplicationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = services.update_application_status(
            request.user.id,
            application_id,
            serializer.validated_data["status"],
        )
        return Response(RecruiterApplicationSerializer(application).data)


class RecruiterApplicationResumeView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={
            200: OpenApiTypes.BINARY,
            404: OpenApiResponse(description="APPLICATION_NOT_FOUND or RESUME_NOT_FOUND"),
        },
        description="Download the applicant's resume (PDF, attachment).",
    )
    def get(self, request: Request, application_id: str) -> FileResponse:
        application = services.get_recruiter_application(request.user.id, application_id)
        return resume.resume_response(application.candidate)


class RecruiterApplicationCountsView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={200: JobApplicationCountSerializer(many=True)},
        description="Applicant counts per role, zero included, for the recruiter's roles.",
    )
    def get(self, request: Request) -> Response:
        data = services.recruiter_application_counts(request.user.id)
        return Response(JobApplicationCountSerializer(data, many=True).data)


class RecruiterDashboardView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={200: RecruiterDashboardSerializer},
        description="Applicant totals by status plus the five most recent applications.",
    )
    def get(self, request: Request) -> Response:
        data = services.recruiter_dashboard(request.user.id)
        return Response(RecruiterDashboardSerializer(data).data)
