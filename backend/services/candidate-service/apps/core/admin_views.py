"""Admin-site login.

The admin page (frontend `/admin`) asks for the credentials that live in the
service `.env` (``ADMIN_USERNAME`` / ``ADMIN_PASSWORD``). A successful login
returns the service's ``INTERNAL_TOKEN`` so the operator never has to paste a
token by hand. The route is unauthenticated by design but throttled like the
user auth routes, and it fails closed when the credentials are not set.
"""

from __future__ import annotations

import hmac

from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import AuthRateThrottle
from config.exceptions import ApiError


class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(
        max_length=256, trim_whitespace=False, style={"input_type": "password"}
    )


class AdminLoginView(APIView):
    """Trade the env-configured admin credentials for this service's internal token."""

    authentication_classes: list[type] = []
    permission_classes: list[type] = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        request=AdminLoginSerializer,
        responses={200: OpenApiTypes.OBJECT, 401: OpenApiTypes.OBJECT, 503: OpenApiTypes.OBJECT},
        description=(
            "Admin-site login. Reads ADMIN_USERNAME / ADMIN_PASSWORD from the service "
            "environment and returns {service, token} on success. The token is the "
            "shared X-Internal-Token used by /internal/admin/*."
        ),
    )
    def post(self, request: Request) -> Response:
        expected_user = settings.ADMIN_USERNAME
        expected_password = settings.ADMIN_PASSWORD
        if not expected_user or not expected_password or not settings.INTERNAL_TOKEN:
            raise ApiError(
                code="ADMIN_LOGIN_DISABLED",
                message="Admin login is not configured for this service.",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = AdminLoginSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        user_ok = hmac.compare_digest(
            payload.validated_data["username"].encode("utf-8"), expected_user.encode("utf-8")
        )
        password_ok = hmac.compare_digest(
            payload.validated_data["password"].encode("utf-8"), expected_password.encode("utf-8")
        )
        if not (user_ok and password_ok):
            raise ApiError(
                code="INVALID_CREDENTIALS",
                message="Invalid username or password.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response({"service": "candidate", "token": settings.INTERNAL_TOKEN})
