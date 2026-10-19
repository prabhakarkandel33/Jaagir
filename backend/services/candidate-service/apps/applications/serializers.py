"""Application input/output serializers."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.applications.models import Application


class ApplicationSerializer(serializers.ModelSerializer[Application]):
    job_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "job_id",
            "status",
            "cover_letter",
            "job_title_snapshot",
            "company_snapshot",
            "applied_at",
            "status_updated_at",
        ]
        read_only_fields = fields


class ApplySerializer(serializers.Serializer[Any]):
    cover_letter = serializers.CharField(required=False, allow_blank=True, default="")


class ApplicationStatusSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(
        choices=[
            "IN_REVIEW",
            "SHORTLISTED",
            "REJECTED",
            "ACCEPTED",
        ]
    )
