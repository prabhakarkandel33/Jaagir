"""Candidate auth and profile endpoints."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.candidates import resume, services
from apps.candidates.serializers import (
    CandidateSerializer,
    CandidateUpdateSerializer,
    LoginSerializer,
    RefreshSerializer,
    RegisterSerializer,
    ResumeUploadSerializer,
)
from apps.core.permissions import IsCandidate
from apps.core.throttling import AuthRateThrottle
from config.exceptions import ApiError


def _auth_response(candidate: Any, http_status: int) -> Response:
    refresh = services.issue_refresh_token(candidate)
    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "tokenType": "Bearer",
            "expiresIn": 3600,
            "refreshExpiresIn": 604800,
            "candidate": CandidateSerializer(candidate).data,
        },
        status=http_status,
    )


class CandidateRegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: CandidateSerializer,
            409: OpenApiResponse(description="Email already registered."),
        },
        description="Create a candidate account and return an access token.",
    )
    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        candidate = services.register_candidate(serializer.validated_data)
        return _auth_response(candidate, status.HTTP_201_CREATED)


class CandidateLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: CandidateSerializer,
            401: OpenApiResponse(description="Invalid credentials."),
        },
        description="Exchange credentials for an access token.",
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        candidate = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if candidate is None or not candidate.is_active:
            raise ApiError(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        return _auth_response(candidate, status.HTTP_200_OK)


class CandidateRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        request=RefreshSerializer,
        responses={
            200: OpenApiResponse(description="New access and refresh tokens."),
            401: OpenApiResponse(description="INVALID_REFRESH_TOKEN"),
        },
        description="Exchange a candidate refresh token for a new access token.",
    )
    def post(self, request: Request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.refresh_tokens(serializer.validated_data["refresh"]))


class CandidateMeView(APIView):
    permission_classes = [IsCandidate]

    @extend_schema(
        responses={200: CandidateSerializer},
        description="The authenticated candidate's profile.",
    )
    def get(self, request: Request) -> Response:
        return Response(CandidateSerializer(request.user).data)

    @extend_schema(
        request=CandidateUpdateSerializer,
        responses={200: CandidateSerializer},
        description="Replace the editable profile fields (email is immutable).",
    )
    def put(self, request: Request) -> Response:
        serializer = CandidateUpdateSerializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        candidate = services.update_candidate(request.user, serializer.validated_data)
        return Response(CandidateSerializer(candidate).data)


class CandidateResumeView(APIView):
    permission_classes = [IsCandidate]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        responses={
            200: OpenApiTypes.BINARY,
            404: OpenApiResponse(description="RESUME_NOT_FOUND"),
        },
        description="Download your own resume (PDF, attachment).",
    )
    def get(self, request: Request) -> FileResponse:
        return resume.resume_response(request.user)

    @extend_schema(
        request=ResumeUploadSerializer,
        responses={
            200: CandidateSerializer,
            400: OpenApiResponse(description="INVALID_RESUME_FILE or RESUME_TOO_LARGE"),
        },
        description="Upload or replace your resume (PDF, max 5 MB).",
    )
    def post(self, request: Request) -> Response:
        serializer = ResumeUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        candidate = resume.save_resume(request.user, serializer.validated_data["file"])
        return Response(CandidateSerializer(candidate).data)

    @extend_schema(
        responses={200: CandidateSerializer},
        description="Remove your uploaded resume.",
    )
    def delete(self, request: Request) -> Response:
        candidate = resume.remove_resume(request.user)
        return Response(CandidateSerializer(candidate).data)
