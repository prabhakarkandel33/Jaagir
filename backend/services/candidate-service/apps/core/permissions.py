"""Role-based permission classes.

Tokens carry a ``role`` claim (ARCHITECTURE.md section 9). Each service checks
the role on every route instead of trusting the token's issuer alone.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


def _role(request: Request) -> str | None:
    token = request.auth
    if token is None:
        return None
    return token.get("role")


class IsCandidate(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user and request.user.is_authenticated and _role(request) == "candidate"
        )


class IsRecruiter(BasePermission):
    """Used for the recruiter-facing route: the JWT is issued by the Job Service."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user and request.user.is_authenticated and _role(request) == "recruiter"
        )
