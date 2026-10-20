from __future__ import annotations

from django.urls import path

from apps.events import views

urlpatterns = [
    path(
        "internal/admin/reconcile",
        views.ReconcileAdminView.as_view(),
        name="internal-reconcile",
    ),
    path(
        "internal/admin/sync-status",
        views.SyncStatusView.as_view(),
        name="internal-sync-status",
    ),
    path(
        "internal/admin/dlq/replay",
        views.DlqReplayView.as_view(),
        name="internal-dlq-replay",
    ),
]
