"""Job input/output serializers."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.jobs.models import Job


class JobSerializer(serializers.ModelSerializer[Job]):
    """Full job representation returned to its owner."""

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "description",
            "company",
            "location",
            "employment_type",
            "skills",
            "status",
            "version",
            "published_at",
            "closed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class JobWriteSerializer(serializers.ModelSerializer[Job]):
    """Create/update payload. Status changes go through the command routes."""

    class Meta:
        model = Job
        fields = ["title", "description", "company", "location", "employment_type", "skills"]
        extra_kwargs = {
            "title": {"max_length": 200},
            "company": {"max_length": 200},
            "location": {"max_length": 200},
            "skills": {"required": False},
        }

    def validate_skills(self, value: Any) -> list[str]:
        if value is None:
            return []
        cleaned = [str(skill).strip() for skill in value if str(skill).strip()]
        return cleaned
