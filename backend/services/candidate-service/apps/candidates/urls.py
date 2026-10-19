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
        "candidates/me",
        views.CandidateMeView.as_view(),
        name="candidate-me",
    ),
]
