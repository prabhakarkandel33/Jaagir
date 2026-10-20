"""Application input/output serializers."""

from __future__ import annotations

from typing import Any

from django.urls import reverse
from rest_framework import serializers

from apps.applications.models import Application
from apps.candidates.models import Candidate
from apps.jobs.models import Job


class ApplicationSerializer(serializers.ModelSerializer[Application]):
    """Lean candidate-facing history row (M7A keeps this one small)."""

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


class JobSnapshotSerializer(serializers.ModelSerializer[Job]):
    """Current replica state of the job an application points at."""

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
            "published_at",
            "closed_at",
        ]
        read_only_fields = fields


class CandidateApplicationDetailSerializer(ApplicationSerializer):
    job = JobSnapshotSerializer(read_only=True)

    class Meta(ApplicationSerializer.Meta):
        fields = [*ApplicationSerializer.Meta.fields, "job"]
        read_only_fields = fields


class CandidateSummarySerializer(serializers.ModelSerializer[Candidate]):
    """Profile fields a recruiter may see for an applicant to their own job."""

    has_resume = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "headline",
            "location",
            "skills",
            "summary",
            "resume_filename",
            "has_resume",
        ]
        read_only_fields = fields

    def get_has_resume(self, obj: Candidate) -> bool:
        return bool(obj.resume_file)


class RecruiterApplicationSerializer(serializers.ModelSerializer[Application]):
    """Applicant plus profile for the recruiter who owns the job."""

    candidate = serializers.SerializerMethodField()
    job = JobSnapshotSerializer(read_only=True)
    resume_url = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "status",
            "cover_letter",
            "applied_at",
            "status_updated_at",
            "job_title_snapshot",
            "company_snapshot",
            "candidate",
            "job",
            "resume_url",
        ]
        read_only_fields = fields

    def get_resume_url(self, obj: Application) -> str:
        if not obj.candidate.resume_file:
            return ""
        return reverse(
            "recruiter-application-resume",
            kwargs={"application_id": obj.id},
        )

    def get_candidate(self, obj: Application) -> dict[str, Any]:
        data = dict(CandidateSummarySerializer(obj.candidate).data)
        # The resume lives behind the application-specific guarded route.
        data["resume_url"] = self.get_resume_url(obj)
        return data


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


class StatusBreakdownSerializer(serializers.Serializer[Any]):
    total = serializers.IntegerField(read_only=True)
    byStatus = serializers.DictField(child=serializers.IntegerField(), read_only=True)


class RecruiterApplicationBreakdownSerializer(StatusBreakdownSerializer):
    newCount = serializers.IntegerField(read_only=True)


class CandidateDashboardSerializer(serializers.Serializer[Any]):
    applications = StatusBreakdownSerializer(read_only=True)
    recent = ApplicationSerializer(many=True, read_only=True)


class RecruiterDashboardSerializer(serializers.Serializer[Any]):
    applications = RecruiterApplicationBreakdownSerializer(read_only=True)
    recent = RecruiterApplicationSerializer(many=True, read_only=True)


class JobApplicationCountSerializer(serializers.Serializer[Any]):
    jobId = serializers.UUIDField(read_only=True)
    total = serializers.IntegerField(read_only=True)
    byStatus = serializers.DictField(child=serializers.IntegerField(), read_only=True)
