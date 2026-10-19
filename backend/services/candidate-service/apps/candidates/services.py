"""Candidate domain logic. Views stay thin; the work lives here."""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.candidates.models import Candidate
from config.exceptions import ApiError

ROLE = "candidate"


def issue_access_token(candidate: Candidate) -> str:
    """Mint a short-lived access token carrying the ``role`` claim."""
    refresh = RefreshToken.for_user(candidate)
    refresh["role"] = ROLE
    return str(refresh.access_token)


def register_candidate(data: dict[str, Any]) -> Candidate:
    """Create a candidate. A duplicate email maps to 409, race-safe."""
    try:
        with transaction.atomic():
            return Candidate.objects.create_user(
                email=data["email"],
                password=data["password"],
                full_name=data["full_name"],
                phone=data.get("phone", ""),
            )
    except IntegrityError as exc:
        raise ApiError(
            code="EMAIL_ALREADY_EXISTS",
            message="An account with this email already exists.",
            http_status=status.HTTP_409_CONFLICT,
        ) from exc


def update_candidate(candidate: Candidate, data: dict[str, Any]) -> Candidate:
    for field in ("full_name", "phone", "headline", "location", "skills", "summary", "resume_url"):
        if field in data:
            setattr(candidate, field, data[field])
    candidate.save()
    return candidate
