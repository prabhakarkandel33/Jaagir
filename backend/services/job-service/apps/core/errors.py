"""JSON handlers for errors raised outside DRF (404/500)."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse


def json_404(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": "NOT_FOUND", "message": "Not found.", "details": {}}},
        status=404,
    )


def json_500(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error.",
                "details": {},
            }
        },
        status=500,
    )
