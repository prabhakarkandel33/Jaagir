"""URL configuration for the Job Service."""

from __future__ import annotations

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

handler404 = "apps.core.errors.json_404"
handler500 = "apps.core.errors.json_500"

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.recruiters.urls")),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
