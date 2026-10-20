from __future__ import annotations

from django.urls import path

from apps.recruiters import views

urlpatterns = [
    path(
        "auth/recruiters/register",
        views.RecruiterRegisterView.as_view(),
        name="recruiter-register",
    ),
    path(
        "auth/recruiters/login",
        views.RecruiterLoginView.as_view(),
        name="recruiter-login",
    ),
    path(
        "auth/recruiters/refresh",
        views.RecruiterRefreshView.as_view(),
        name="recruiter-refresh",
    ),
    path(
        "recruiters/me",
        views.RecruiterMeView.as_view(),
        name="recruiter-me",
    ),
]
