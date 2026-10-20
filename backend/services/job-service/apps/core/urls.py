from __future__ import annotations

from django.urls import path

from apps.core import admin_views, views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("readyz", views.readyz, name="readyz"),
    path("internal/admin/login", admin_views.AdminLoginView.as_view(), name="internal-admin-login"),
]
