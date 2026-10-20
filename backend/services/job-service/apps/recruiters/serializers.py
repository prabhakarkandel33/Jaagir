"""Recruiter input/output serializers."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.recruiters.models import Recruiter


class RecruiterSerializer(serializers.ModelSerializer[Recruiter]):
    """Public recruiter profile. Never exposes the password hash."""

    class Meta:
        model = Recruiter
        fields = [
            "id",
            "email",
            "full_name",
            "company_name",
            "phone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    full_name = serializers.CharField(max_length=200)
    company_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
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


class RecruiterUpdateSerializer(serializers.ModelSerializer[Recruiter]):
    """Editable profile fields for PUT /recruiters/me. Email is immutable."""

    class Meta:
        model = Recruiter
        fields = ["full_name", "company_name", "phone"]
        extra_kwargs = {
            "full_name": {"required": True, "max_length": 200},
            "company_name": {"required": False, "max_length": 200},
            "phone": {"required": False, "max_length": 50},
        }
