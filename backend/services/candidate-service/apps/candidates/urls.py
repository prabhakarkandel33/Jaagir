from __future__ import annotations

from django.urls import path

from apps.candidates import views

urlpatterns = [
    path(
        "auth/candidates/register",
        views.CandidateRegisterView.as_view(),
        name="candidate-register",
    ),
    path(
        "auth/candidates/login",
        views.CandidateLoginView.as_view(),
        name="candidate-login",
    ),
    path(
        "auth/candidates/refresh",
        views.CandidateRefreshView.as_view(),
        name="candidate-refresh",
    ),
    path(
        "candidates/me",
        views.CandidateMeView.as_view(),
        name="candidate-me",
    ),
    path(
        "candidates/me/resume",
        views.CandidateResumeView.as_view(),
        name="candidate-resume",
    ),
]
