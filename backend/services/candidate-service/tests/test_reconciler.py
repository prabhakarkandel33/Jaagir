"""Reconciliation (M6).

The reconciler is the safety net for LOST events. These tests prove that it
repairs a stale or missing replica, never downgrades a newer local row, never
deletes an unknown local row, and records every pass.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.events.models import ReconcileRun
from apps.events.reconciler import MODE_FULL, MODE_INCREMENTAL, reconcile
from apps.jobs.models import Job, JobStatus
from apps.jobs.services import upsert_job_from_snapshot
from contracts import EmploymentType, JobSnapshot
from contracts import JobStatus as ContractJobStatus

NOW = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

pytestmark = pytest.mark.django_db
TOKEN = "test-internal-token"
HEADERS = {"HTTP_X_INTERNAL_TOKEN": TOKEN}


def snapshot(
    *,
    job_id: Any | None = None,
    version: int = 2,
    title: str = "Backend Engineer",
    status: ContractJobStatus = ContractJobStatus.PUBLISHED,
) -> JobSnapshot:
    return JobSnapshot(
        id=job_id or uuid4(),
        recruiter_id=uuid4(),
        title=title,
        description="Build services",
        company="Example",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        skills=["python"],
        status=status,
        version=version,
        published_at=NOW,
        closed_at=None,
        updated_at=NOW,
    )


def page_client(pages: list[list[JobSnapshot]]) -> Any:
    """Fake Job Service client: returns each page once, then an empty page."""
    calls: list[dict[str, Any]] = []
    queue = list(pages)

    def _client(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        items = queue.pop(0) if queue else []
        return {
            "items": [item.model_dump(mode="json", by_alias=True) for item in items],
            "nextAfter": str(items[-1].id) if items and queue else None,
            "hasMore": bool(items and queue),
        }

    _client.calls = calls  # type: ignore[attr-defined]
    return _client


def test_full_reconcile_repairs_missing_rows() -> None:
    snaps = [snapshot(version=3), snapshot(version=5)]
    for item in snaps:
        assert Job.objects.filter(id=item.id).exists() is False

    run = reconcile(MODE_FULL, client=page_client([snaps]))

    assert run.checked == 2
    assert run.repaired == 2
    assert run.error is None
    assert run.finished_at is not None
    for item in snaps:
        row = Job.objects.get(id=item.id)
        assert row.version == item.version
        assert row.status == JobStatus.PUBLISHED


def test_full_reconcile_repairs_stale_versions() -> None:
    stale = snapshot(version=2)
    upsert_job_from_snapshot(stale)
    newer = snapshot(job_id=stale.id, version=7, title="Renamed")

    run = reconcile(MODE_FULL, client=page_client([[newer]]))

    assert run.repaired == 1
    row = Job.objects.get(id=stale.id)
    assert row.version == 7
    assert row.title == "Renamed"


def test_reconcile_never_downgrades_a_newer_local_row() -> None:
    fresh = snapshot(version=9, title="Local wins")
    upsert_job_from_snapshot(fresh)
    older = snapshot(job_id=fresh.id, version=4, title="Source is behind")

    run = reconcile(MODE_FULL, client=page_client([[older]]))

    assert run.repaired == 0
    row = Job.objects.get(id=fresh.id)
    assert row.version == 9
    assert row.title == "Local wins"


def test_full_reconcile_does_not_delete_unknown_local_rows() -> None:
    ghost = snapshot(version=2)
    upsert_job_from_snapshot(ghost)

    run = reconcile(MODE_FULL, client=page_client([[]]))

    assert run.checked == 0
    assert Job.objects.filter(id=ghost.id).exists()


def test_each_pass_writes_one_run_row() -> None:
    reconcile(MODE_FULL, client=page_client([[snapshot()]]))
    reconcile(MODE_FULL, client=page_client([[snapshot()]]))
    assert ReconcileRun.objects.count() == 2
    assert set(ReconcileRun.objects.values_list("mode", flat=True)) == {MODE_FULL}


def test_incremental_pass_uses_an_overlap_window() -> None:
    client = page_client([[]])
    ReconcileRun.objects.create(mode=MODE_FULL, started_at=NOW, finished_at=NOW)

    reconcile(MODE_INCREMENTAL, client=client)

    sent = client.calls[0]["updated_after"]
    assert sent is not None
    assert "-10" in sent or "01-01T09:50" in sent


def test_full_pass_sends_no_updated_after() -> None:
    client = page_client([[]])
    reconcile(MODE_FULL, client=client)
    assert client.calls[0]["updated_after"] is None


def test_failed_pass_is_recorded_and_reraised() -> None:
    def _boom(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("job service down")

    with pytest.raises(RuntimeError):
        reconcile(MODE_FULL, client=_boom)

    run = ReconcileRun.objects.first()
    assert run is not None
    assert run.error == "job service down"
    assert run.finished_at is not None


def test_reconcile_endpoint_requires_token() -> None:
    response = APIClient().post("/internal/admin/reconcile")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_reconcile_endpoint_rejects_bad_mode() -> None:
    response = APIClient().post("/internal/admin/reconcile?mode=nightly", **HEADERS)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@override_settings(INTERNAL_TOKEN=TOKEN, JOB_SERVICE_INTERNAL_URL="http://127.0.0.1:9")
def test_reconcile_endpoint_reports_unreachable_peer() -> None:
    response = APIClient().post("/internal/admin/reconcile?mode=full", **HEADERS)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "JOB_SERVICE_UNAVAILABLE"


@override_settings(INTERNAL_TOKEN=TOKEN)
def test_sync_status_requires_token_and_reports_last_run() -> None:
    assert APIClient().get("/internal/admin/sync-status").status_code == 401

    ReconcileRun.objects.create(
        mode=MODE_FULL, started_at=NOW, finished_at=NOW, checked=3, repaired=2
    )
    body = APIClient().get("/internal/admin/sync-status", **HEADERS).json()
    assert body["lastRepaired"] == 2
    assert body["lastRun"]["mode"] == MODE_FULL
    assert body["localJobCount"] == 0
