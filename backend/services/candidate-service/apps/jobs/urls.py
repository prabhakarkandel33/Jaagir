from __future__ import annotations

from django.urls import path

from apps.jobs import views

urlpatterns = [
    path("jobs", views.JobSearchView.as_view(), name="job-search"),
    path("jobs/<uuid:job_id>", views.JobDetailView.as_view(), name="job-detail"),
]
