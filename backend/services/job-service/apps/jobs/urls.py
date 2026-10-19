from __future__ import annotations

from django.urls import path

from apps.jobs import views

urlpatterns = [
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
    path("jobs/<uuid:job_id>", views.PublicJobDetailView.as_view(), name="public-job-detail"),
]
