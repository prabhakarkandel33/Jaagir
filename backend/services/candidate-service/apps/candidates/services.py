"""Candidate domain logic. Views stay thin; the work lives here."""

from __future__ import annotations

from typing import Any, cast

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.candidates.models import Candidate
from config.exceptions import ApiError

ROLE = "candidate"


def issue_refresh_token(candidate: Candidate) -> RefreshToken:
    """Refresh token carrying ``role``/``iss``; access tokens inherit both."""
    refresh = RefreshToken.for_user(candidate)
    refresh["role"] = ROLE
    return refresh


def issue_access_token(candidate: Candidate) -> str:
    """Mint a short-lived access token carrying the ``role`` claim."""
    return str(issue_refresh_token(candidate).access_token)


def refresh_tokens(raw_refresh: str) -> dict[str, Any]:
    """Exchange a candidate refresh token for a fresh access/refresh pair."""
    try:
        refresh = RefreshToken(cast(Any, raw_refresh))
    except TokenError:
        raise _invalid_refresh() from None
    if refresh.get("role") != ROLE:
        raise _invalid_refresh()

    user_id = refresh.get(api_settings.USER_ID_CLAIM)
    candidate = Candidate.objects.filter(id=user_id, is_active=True).first()
    if candidate is None:
        raise _invalid_refresh()

    new_refresh = issue_refresh_token(candidate)
    return {
        "access": str(new_refresh.access_token),
        "refresh": str(new_refresh),
        "tokenType": "Bearer",
        "expiresIn": 3600,
        "refreshExpiresIn": 604800,
    }


def _invalid_refresh() -> ApiError:
    return ApiError(
        code="INVALID_REFRESH_TOKEN",
        message="The refresh token is invalid or expired.",
        http_status=status.HTTP_401_UNAUTHORIZED,
    )


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
