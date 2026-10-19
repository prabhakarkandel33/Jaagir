"""Guard for internal endpoints (invariant I8).

Caddy returns 404 for ``/internal/*`` from the public internet (M7); at the
application layer every internal route additionally requires the shared
``X-Internal-Token`` header, compared in constant time.
"""

from __future__ import annotations

import hmac

from django.conf import settings
from rest_framework import status
from rest_framework.request import Request

from config.exceptions import ApiError


def is_internal_request(request: Request) -> bool:
    expected = settings.INTERNAL_TOKEN
    if not expected:
        return False
    provided = request.headers.get("X-Internal-Token", "")
    return hmac.compare_digest(provided, expected)


def require_internal(request: Request) -> None:
    if not is_internal_request(request):
        raise ApiError(
            code="UNAUTHORIZED",
            message="A valid X-Internal-Token header is required.",
            http_status=status.HTTP_401_UNAUTHORIZED,
        )
