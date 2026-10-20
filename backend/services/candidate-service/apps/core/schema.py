"""OpenAPI security scheme for the issuer-aware JWT authentication."""

from __future__ import annotations

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class IssuerAwareJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.core.authentication.IssuerAwareJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, Any]:
        del auto_schema
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
