"""Candidate input/output serializers."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.candidates.models import Candidate


class CandidateSerializer(serializers.ModelSerializer[Candidate]):
    """Candidate profile. Never exposes the password hash or a media path."""

    has_resume = serializers.SerializerMethodField()
    resume_url = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "headline",
            "location",
            "skills",
            "summary",
            "resume_url",
            "resume_filename",
            "resume_uploaded_at",
            "has_resume",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_has_resume(self, obj: Candidate) -> bool:
        return bool(obj.resume_file)

    def get_resume_url(self, obj: Candidate) -> str:
        # Guarded endpoint, not a media URL. Empty when nothing is uploaded.
        if obj.resume_file:
            return "/candidates/me/resume"
        return obj.resume_url


class RegisterSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    full_name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class LoginSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, max_length=128)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class RefreshSerializer(serializers.Serializer[Any]):
    refresh = serializers.CharField()


class ResumeUploadSerializer(serializers.Serializer[Any]):
    # Empty files reach ``resume.validate_pdf`` so the error code stays stable.
    file = serializers.FileField(allow_empty_file=True)


class CandidateUpdateSerializer(serializers.ModelSerializer[Candidate]):
    """Editable profile fields for PUT /candidates/me. Email is immutable."""

    class Meta:
        model = Candidate
        fields = ["full_name", "phone", "headline", "location", "skills", "summary", "resume_url"]
        extra_kwargs = {
            "full_name": {"required": True, "max_length": 200},
            "phone": {"required": False, "max_length": 50},
            "headline": {"required": False, "max_length": 200},
            "location": {"required": False, "max_length": 200},
            "skills": {"required": False},
            "summary": {"required": False},
            "resume_url": {"required": False, "max_length": 500},
        }
