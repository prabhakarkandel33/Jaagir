"""HTTP client for the Job Service internal snapshot API (M6).

Uses stdlib ``urllib`` (no extra dependency). Every call carries the shared
``X-Internal-Token`` (invariant I8). Failures raise ``JobServiceUnavailable``
so callers can log and retry next cycle instead of crashing.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings


class JobServiceUnavailable(RuntimeError):
    """The peer service did not answer with a usable page."""


def fetch_snapshot_page(
    *,
    after: str | None = None,
    limit: int = 500,
    updated_after: str | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Fetch one keyset page of job snapshots from the Job Service."""
    params: dict[str, str] = {"limit": str(limit)}
    if after:
        params["after"] = after
    if updated_after:
        params["updatedAfter"] = updated_after

    url = f"{settings.JOB_SERVICE_INTERNAL_URL.rstrip('/')}/internal/jobs/snapshot"
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(  # noqa: S310
        f"{url}?{query}",
        headers={"X-Internal-Token": settings.INTERNAL_TOKEN, "Accept": "application/json"},
        method="GET",
    )
    timeout = settings.RECONCILE_HTTP_TIMEOUT_SECONDS if timeout_s is None else timeout_s
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise JobServiceUnavailable(str(exc)) from exc
    if not isinstance(payload, dict) or "items" not in payload:
        raise JobServiceUnavailable("unexpected snapshot response")
    return payload
