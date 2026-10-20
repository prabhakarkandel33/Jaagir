"""Recruiter domain logic. Views stay thin; the work lives here."""

from __future__ import annotations

from typing import Any, cast

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.recruiters.models import Recruiter
from config.exceptions import ApiError

ROLE = "recruiter"


def issue_refresh_token(recruiter: Recruiter) -> RefreshToken:
    """Refresh token carrying ``role``/``iss``; access tokens inherit both."""
    refresh = RefreshToken.for_user(recruiter)
    refresh["role"] = ROLE
    return refresh


def issue_access_token(recruiter: Recruiter) -> str:
    """Mint a short-lived access token carrying the ``role`` claim.

    ``sub`` is set to the user id by SimpleJWT and ``iss`` comes from the
    ``ISSUER`` setting; we only add the service-specific role.
    """
    return str(issue_refresh_token(recruiter).access_token)


def _invalid_refresh() -> ApiError:
    return ApiError(
        code="INVALID_REFRESH_TOKEN",
        message="The refresh token is invalid or expired.",
        http_status=status.HTTP_401_UNAUTHORIZED,
    )


def refresh_tokens(raw_refresh: str) -> dict[str, Any]:
    """Exchange a recruiter refresh token for a fresh access/refresh pair."""
    try:
        refresh = RefreshToken(cast(Any, raw_refresh))
    except TokenError:
        raise _invalid_refresh() from None
    if refresh.get("role") != ROLE:
        raise _invalid_refresh()

    user_id = refresh.get(api_settings.USER_ID_CLAIM)
    recruiter = Recruiter.objects.filter(id=user_id, is_active=True).first()
    if recruiter is None:
        raise _invalid_refresh()

    new_refresh = issue_refresh_token(recruiter)
    return {
        "access": str(new_refresh.access_token),
        "refresh": str(new_refresh),
        "tokenType": "Bearer",
        "expiresIn": 3600,
        "refreshExpiresIn": 604800,
    }


def register_recruiter(data: dict[str, Any]) -> Recruiter:
    """Create a recruiter. A duplicate email maps to 409, race-safe.

    Uniqueness is enforced by the database (lower(email)); we never
    check-then-insert, so concurrent registrations cannot both succeed.
    """
    try:
        with transaction.atomic():
            return Recruiter.objects.create_user(
                email=data["email"],
                password=data["password"],
                full_name=data["full_name"],
                company_name=data.get("company_name", ""),
                phone=data.get("phone", ""),
            )
    except IntegrityError as exc:
        raise ApiError(
            code="EMAIL_ALREADY_EXISTS",
            message="An account with this email already exists.",
            http_status=status.HTTP_409_CONFLICT,
        ) from exc


def update_recruiter(recruiter: Recruiter, data: dict[str, Any]) -> Recruiter:
    recruiter.full_name = data["full_name"]
    recruiter.company_name = data.get("company_name", "")
    recruiter.phone = data.get("phone", "")
    recruiter.save(update_fields=["full_name", "company_name", "phone", "updated_at"])
    return recruiter
