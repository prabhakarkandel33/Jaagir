from __future__ import annotations

from django.urls import path

from apps.core import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("readyz", views.readyz, name="readyz"),
]
