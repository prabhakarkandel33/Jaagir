from __future__ import annotations

from django.urls import path

from apps.jobs import views

urlpatterns = [
    path("jobs/<uuid:job_id>", views.JobDetailView.as_view(), name="job-detail"),
]
