"""Uniform API error format and DRF exception handling.

Every error response has the shape (AGENTS.md section 6):

    {"error": {"code": "SCREAMING_SNAKE", "message": "...", "details": {}}}
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

_STATUS_TO_CODE = {
    status.HTTP_400_BAD_REQUEST: "VALIDATION_ERROR",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHENTICATED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
}


class ApiError(APIException):
    """Domain error: raise with a SCREAMING_SNAKE code and a status."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = code
        self.error_message = message
        self.error_details = details or {}
        super().__init__(message)
        # DRF reads ``status_code`` from the instance, not from ``code`` (which
        # is a machine-readable string). Set both.
        self.status_code = http_status
        self.code = code


def _field_label(name: str) -> str:
    if name == "non_field_errors":
        return "Request"
    return name.replace("_", " ").capitalize()


def _message_from_detail(detail: Any, field: str = "") -> str:
    """Turn a DRF validation tree into a readable, field-aware message."""
    if isinstance(detail, dict):
        parts: list[str] = []
        for key, value in detail.items():
            child = field or _field_label(str(key))
            parts.append(_message_from_detail(value, child))
        return " ".join(part for part in parts if part)
    if isinstance(detail, list):
        return " ".join(_message_from_detail(item, field) for item in detail)
    if isinstance(detail, str):
        if field and detail.lower() == "this field is required.":
            return f"{field} is required."
        return f"{field}: {detail}" if field else detail
    return "Invalid request."


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF EXCEPTION_HANDLER that always returns the uniform error envelope."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    http_status = response.status_code

    if isinstance(exc, ApiError):
        code = exc.error_code
        message = exc.error_message
        details = exc.error_details
    elif isinstance(exc, ValidationError):
        code = "VALIDATION_ERROR"
        message = _message_from_detail(exc.detail) or "Request validation failed."
        details = exc.detail
    else:
        code = _STATUS_TO_CODE.get(http_status, "ERROR")
        message = _message_from_detail(getattr(exc, "detail", response.data))
        details = {}

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }
    return response
