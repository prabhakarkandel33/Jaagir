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
        "candidates/me/dashboard",
        views.CandidateDashboardView.as_view(),
        name="candidate-dashboard",
    ),
    path(
        "recruiter/applications",
        views.RecruiterApplicationListView.as_view(),
        name="recruiter-applications",
    ),
    path(
        "recruiter/application-counts",
        views.RecruiterApplicationCountsView.as_view(),
        name="recruiter-application-counts",
    ),
    path(
        "recruiter/applications/<uuid:application_id>",
        views.RecruiterApplicationDetailView.as_view(),
        name="recruiter-application-detail",
    ),
    path(
        "recruiter/applications/<uuid:application_id>/status",
        views.RecruiterApplicationStatusView.as_view(),
        name="recruiter-application-status",
    ),
    path(
        "recruiter/applications/<uuid:application_id>/resume",
        views.RecruiterApplicationResumeView.as_view(),
        name="recruiter-application-resume",
    ),
    path(
        "recruiter/dashboard",
        views.RecruiterDashboardView.as_view(),
        name="recruiter-dashboard",
    ),
    path(
        "recruiter/jobs/<uuid:job_id>/applications",
        views.RecruiterJobApplicationsView.as_view(),
        name="recruiter-job-applications",
    ),
]
