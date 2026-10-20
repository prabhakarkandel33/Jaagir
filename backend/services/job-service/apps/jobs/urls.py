from __future__ import annotations

from django.urls import path

from apps.jobs import internal_views, views

urlpatterns = [
    path(
        "internal/jobs/snapshot",
        internal_views.InternalJobSnapshotView.as_view(),
        name="internal-job-snapshot",
    ),
    path(
        "internal/jobs/<uuid:job_id>",
        internal_views.InternalJobDetailView.as_view(),
        name="internal-job-detail",
    ),
    path(
        "recruiter/dashboard",
        views.RecruiterDashboardView.as_view(),
        name="recruiter-dashboard",
    ),
    path("recruiter/jobs", views.RecruiterJobListCreateView.as_view(), name="recruiter-jobs"),
    path(
        "recruiter/jobs/<uuid:job_id>",
        views.RecruiterJobDetailView.as_view(),
        name="recruiter-job-detail",
    ),
    path(
        "recruiter/jobs/<uuid:job_id>/publish",
        views.JobPublishView.as_view(),
        name="recruiter-job-publish",
    ),
    path(
        "recruiter/jobs/<uuid:job_id>/close",
        views.JobCloseView.as_view(),
        name="recruiter-job-close",
    ),
    path("jobs", views.PublicJobSearchView.as_view(), name="public-job-search"),
    path("jobs/<uuid:job_id>", views.PublicJobDetailView.as_view(), name="public-job-detail"),
]
