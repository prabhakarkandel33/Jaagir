from __future__ import annotations

from django.urls import path

from apps.applications import views

urlpatterns = [
    path(
        "jobs/<uuid:job_id>/applications",
        views.ApplyView.as_view(),
        name="apply",
    ),
    path(
        "candidates/me/applications",
        views.CandidateApplicationsView.as_view(),
        name="candidate-applications",
    ),
    path(
        "candidates/me/applications/<uuid:application_id>",
        views.CandidateApplicationDetailView.as_view(),
        name="candidate-application-detail",
    ),
    path(
        "recruiter/jobs/<uuid:job_id>/applications",
        views.RecruiterJobApplicationsView.as_view(),
        name="recruiter-job-applications",
    ),
]
