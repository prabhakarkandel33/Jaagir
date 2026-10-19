"""Job replica serializers (read-only: this service never writes job truth)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.jobs.models import EmploymentType, Job


class JobSerializer(serializers.ModelSerializer[Job]):
    class Meta:
        model = Job
        fields = [
            "id",
            "recruiter_id",
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
            "source_updated_at",
        ]
        read_only_fields = fields


class JobSearchParamsSerializer(serializers.Serializer[Any]):
    """Query parameters for the candidate-facing search endpoint."""

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


class JobSearchResultSerializer(serializers.Serializer[Any]):
    """One search hit from the replica."""

    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    company = serializers.CharField(read_only=True)
    location = serializers.CharField(read_only=True)
    employment_type = serializers.CharField(read_only=True)
    skills = serializers.ListField(child=serializers.CharField(), read_only=True)
    published_at = serializers.DateTimeField(read_only=True)
