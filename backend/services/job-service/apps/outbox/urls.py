from __future__ import annotations

from django.urls import path

from apps.outbox import views

urlpatterns = [
    path(
        "internal/admin/outbox",
        views.OutboxAdminView.as_view(),
        name="internal-outbox",
    ),
]
