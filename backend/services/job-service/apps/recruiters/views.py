"""Recruiter auth and profile endpoints."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsRecruiter
from apps.core.throttling import AuthRateThrottle
from apps.recruiters import services
from apps.recruiters.serializers import (
    LoginSerializer,
    RecruiterSerializer,
    RecruiterUpdateSerializer,
    RefreshSerializer,
    RegisterSerializer,
)
from config.exceptions import ApiError


def _auth_response(recruiter: Any, http_status: int) -> Response:
    refresh = services.issue_refresh_token(recruiter)
    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "tokenType": "Bearer",
            "expiresIn": 3600,
            "refreshExpiresIn": 604800,
            "recruiter": RecruiterSerializer(recruiter).data,
        },
        status=http_status,
    )


class RecruiterRegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: RecruiterSerializer,
            409: OpenApiResponse(description="Email already registered."),
        },
        description="Create a recruiter account and return an access token.",
    )
    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recruiter = services.register_recruiter(serializer.validated_data)
        return _auth_response(recruiter, status.HTTP_201_CREATED)


class RecruiterLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: RecruiterSerializer,
            401: OpenApiResponse(description="Invalid credentials."),
        },
        description="Exchange credentials for an access token.",
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recruiter = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if recruiter is None or not recruiter.is_active:
            # Generic message: never reveal whether the email exists.
            raise ApiError(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        return _auth_response(recruiter, status.HTTP_200_OK)


class RecruiterRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        request=RefreshSerializer,
        responses={
            200: OpenApiResponse(description="New access and refresh tokens."),
            401: OpenApiResponse(description="INVALID_REFRESH_TOKEN"),
        },
        description="Exchange a recruiter refresh token for a new access token.",
    )
    def post(self, request: Request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.refresh_tokens(serializer.validated_data["refresh"]))


class RecruiterMeView(APIView):
    permission_classes = [IsRecruiter]

    @extend_schema(
        responses={200: RecruiterSerializer},
        description="The authenticated recruiter's profile.",
    )
    def get(self, request: Request) -> Response:
        return Response(RecruiterSerializer(request.user).data)

    @extend_schema(
        request=RecruiterUpdateSerializer,
        responses={200: RecruiterSerializer},
        description="Replace the editable profile fields (email is immutable).",
    )
    def put(self, request: Request) -> Response:
        serializer = RecruiterUpdateSerializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        recruiter = services.update_recruiter(request.user, serializer.validated_data)
        return Response(RecruiterSerializer(recruiter).data)
