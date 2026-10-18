"""Pagination: ``page`` (1-based) and ``pageSize`` (default 20, max 50).

The response shape is ``{items, page, pageSize, total}`` (AGENTS.md section 6).
"""

from __future__ import annotations

from typing import Any

from rest_framework.pagination import PageNumberPagination as DRFPageNumberPagination
from rest_framework.response import Response


class PageNumberPagination(DRFPageNumberPagination):
    page_size_query_param = "pageSize"
    max_page_size = 50

    def get_paginated_response(self, data: list[Any]) -> Response:
        return Response(
            {
                "items": data,
                "page": self.page.number,
                "pageSize": self.get_page_size(self.request),
                "total": self.page.paginator.count,
            }
        )
