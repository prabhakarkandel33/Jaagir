"""Job input/output serializers."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.jobs.models import EmploymentType, Job


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


class JobSearchParamsSerializer(serializers.Serializer[Any]):
    """Query parameters for the public search endpoint.

    ``q`` is optional: an empty query means "browse", not an error. Values are
    validated here and then travel to SQL as bound parameters only.
    """

    q = serializers.CharField(required=False, allow_blank=True, default="")
    employmentType = serializers.ChoiceField(
        choices=EmploymentType.values,
        required=False,
        allow_blank=True,
        default="",
    )
    location = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    skills = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        default=list,
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)


class JobStatusBreakdownSerializer(serializers.Serializer[Any]):
    total = serializers.IntegerField(read_only=True)
    byStatus = serializers.DictField(child=serializers.IntegerField(), read_only=True)


class RecruiterJobDashboardSerializer(serializers.Serializer[Any]):
    jobs = JobStatusBreakdownSerializer(read_only=True)
    recentJobs = JobSerializer(many=True, read_only=True)


class JobSearchResultSerializer(serializers.Serializer[Any]):
    """One search hit. Deliberately narrower than JobSerializer."""

    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    company = serializers.CharField(read_only=True)
    location = serializers.CharField(read_only=True)
    employment_type = serializers.CharField(read_only=True)
    skills = serializers.ListField(child=serializers.CharField(), read_only=True)
    published_at = serializers.DateTimeField(read_only=True)
