"""Fail-fast environment configuration for the Candidate Service."""

from __future__ import annotations

import base64
import binascii
from functools import lru_cache

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

_EMPTY_KEYS = {"", "change-me", "replace-me"}


def decode_pem(value: str, *, field: str) -> str:
    """Decode a base64-encoded PEM key.

    PEM keys lose their newlines in environment variables, so we ship them as
    base64 and decode at boot (CONTEXT.md gotcha, [2026-10-19, M2]). An empty
    value stays empty so the service can boot before keys are provisioned.
    """
    if value in _EMPTY_KEYS:
        return ""
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{field} must be the base64 encoding of a PEM key") from exc
    if "-----BEGIN" not in decoded:
        raise ValueError(f"{field} did not decode to a PEM block")
    return decoded


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    service_name: str = "candidate-service"
    debug: bool = False
    log_level: str = "INFO"

    # Required: no default. Boot fails when these are absent.
    django_secret_key: str
    database_url: PostgresDsn

    allowed_hosts: str = "*"
    cors_allowed_origins: str = ""
    body_max_bytes: int = 1_048_576

    # Resume media (M7A). Empty MEDIA_ROOT means <service>/media.
    media_root: str = ""
    resume_max_bytes: int = 5_242_880

    # Kafka: consumer settings. Kafka is optional for availability (I9).
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group_id: str = "candidate-service"
    # Background consumer poll loop. Off in tests.
    kafka_consumer_enabled: bool = True
    # How long the DLQ producer waits for a broker ack before it gives up.
    kafka_message_timeout_ms: int = 5000

    # Reconciliation (M6).
    reconcile_enabled: bool = True
    reconcile_incremental_seconds: int = 300
    reconcile_full_seconds: int = 86400
    reconcile_startup_delay_seconds: int = 30
    reconcile_batch_limit: int = 500
    reconcile_http_timeout_seconds: float = 10.0

    # Internal endpoints + talking to the Job Service internally (I8).
    internal_token: str = ""
    job_service_internal_url: str = "http://localhost:3001"

    # Admin site login (frontend `/admin`). Empty disables the login route.
    admin_username: str = ""
    admin_password: str = ""

    # JWT: this service signs candidate tokens; it verifies recruiter tokens
    # with the Job Service public key.
    jwt_signing_key: str = ""
    jwt_public_key: str = ""
    jwt_algorithm: str = "ES256"
    jwt_issuer: str = "candidate-service"
    job_service_jwt_public_key: str = ""

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]

    @property
    def jwt_signing_key_pem(self) -> str:
        return decode_pem(self.jwt_signing_key, field="JWT_SIGNING_KEY")

    @property
    def jwt_public_key_pem(self) -> str:
        return decode_pem(self.jwt_public_key, field="JWT_PUBLIC_KEY")

    @property
    def job_service_jwt_public_key_pem(self) -> str:
        return decode_pem(
            self.job_service_jwt_public_key,
            field="JOB_SERVICE_JWT_PUBLIC_KEY",
        )


@lru_cache
def get_settings() -> ServiceSettings:
    # pydantic-settings fills required fields from the environment/`.env`.
    return ServiceSettings()  # type: ignore[call-arg]
