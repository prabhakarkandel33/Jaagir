"""Job replica serializers (read-only: this service never writes job truth)."""

from __future__ import annotations

from rest_framework import serializers

from apps.jobs.models import Job


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
