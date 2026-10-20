"""Core app: health endpoints, pagination, JSON error handlers."""

from __future__ import annotations

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self) -> None:
        # Registers the security scheme used by drf-spectacular.
        from apps.core import schema  # noqa: F401
