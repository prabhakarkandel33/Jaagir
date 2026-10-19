"""Candidate auth and profile endpoints."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.candidates import services
from apps.candidates.serializers import (
    CandidateSerializer,
    CandidateUpdateSerializer,
    LoginSerializer,
    RegisterSerializer,
)
from apps.core.permissions import IsCandidate
from apps.core.throttling import AuthRateThrottle
from config.exceptions import ApiError


def _auth_response(candidate: Any, http_status: int) -> Response:
    return Response(
        {
            "access": services.issue_access_token(candidate),
            "tokenType": "Bearer",
            "expiresIn": 3600,
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
