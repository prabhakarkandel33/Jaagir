"""Issuer-aware JWT authentication.

The Candidate Service signs its own candidate tokens and accepts recruiter
tokens issued by the Job Service (ARCHITECTURE.md section 9). SimpleJWT has one
verifying key, so this class selects the key from the token's ``iss`` claim:
candidate tokens verify with this service's public key, recruiter tokens with
the Job Service public key from env.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt as pyjwt
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.backends import TokenBackend
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, Token

RECRUITER_ROLE = "recruiter"
CANDIDATE_ROLE = "candidate"


class RecruiterPrincipal:
    """Lightweight principal for a recruiter token.

    The recruiter does not exist in ``candidate_db`` (invariant I1), so routes
    that only need the recruiter's identity and role use this instead of a
    Django user. It carries enough surface for DRF permissions and throttling.
    """

    is_authenticated = True
    is_anonymous = False

    def __init__(self, user_id: UUID, role: str) -> None:
        self.pk = user_id
        self.id = user_id
        self.role = role

    def __str__(self) -> str:
        return f"{self.role}:{self.pk}"


def _peek_claims(raw_token: bytes) -> dict[str, Any]:
    # Signature and issuer checks are off: this only reads ``iss`` so we can
    # choose the right verifying key. The keyed token below does the real work.
    return pyjwt.decode(
        raw_token,
        options={
            "verify_signature": False,
            "verify_exp": False,
            "verify_aud": False,
            "verify_iss": False,
        },
        algorithms=[api_settings.ALGORITHM],
    )


@lru_cache(maxsize=4)
def _token_class_for(verifying_key: str) -> type[AccessToken]:
    class _KeyedAccessToken(AccessToken):
        def get_token_backend(self) -> TokenBackend:
            return TokenBackend(
                algorithm=api_settings.ALGORITHM,
                signing_key=None,
                verifying_key=verifying_key,
                audience=None,
                issuer=None,
                leeway=api_settings.LEEWAY,
                json_encoder=api_settings.JSON_ENCODER,
            )

    return _KeyedAccessToken


class IssuerAwareJWTAuthentication(JWTAuthentication):
    def _verifying_key_for(self, issuer: Any) -> str:
        job_issuer = getattr(settings, "JOB_SERVICE_JWT_ISSUER", "job-service")
        if issuer == job_issuer:
            key = getattr(settings, "JOB_SERVICE_JWT_PUBLIC_KEY", "")
            if not key:
                raise InvalidToken({"detail": "Recruiter tokens are not configured."})
            return key
        if issuer == settings.SIMPLE_JWT["ISSUER"]:
            return str(settings.SIMPLE_JWT["VERIFYING_KEY"])
        raise InvalidToken({"detail": "Token issuer is not accepted here."})

    def get_validated_token(self, raw_token: bytes) -> Token:
        try:
            claims = _peek_claims(raw_token)
        except pyjwt.PyJWTError as exc:
            raise InvalidToken({"detail": "Token is invalid or expired."}) from exc

        verifying_key = self._verifying_key_for(claims.get("iss"))
        try:
            return _token_class_for(verifying_key)(raw_token)  # type: ignore[arg-type]
        except TokenError as exc:
            raise InvalidToken({"detail": "Token is invalid or expired."}) from exc

    def get_user(self, validated_token: Token) -> Any:
        if validated_token.get("role") == RECRUITER_ROLE:
            user_id = validated_token.get(api_settings.USER_ID_CLAIM)
            return RecruiterPrincipal(user_id, RECRUITER_ROLE)
        return super().get_user(validated_token)
