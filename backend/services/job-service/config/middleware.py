"""Request id middleware: one id per request, echoed in the response."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from django.http import HttpRequest, HttpResponse

from config.observability import set_request_id

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        request.request_id = request_id  # type: ignore[attr-defined]
        set_request_id(request_id)
        response = self.get_response(request)
        response[REQUEST_ID_HEADER] = request_id
        return response
