"""Fail-fast environment configuration for the Job Service.

One ``ServiceSettings`` object per service. It is built once, at import of the
settings module. A missing required variable stops the boot immediately.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    service_name: str = "job-service"
    debug: bool = False
    log_level: str = "INFO"

    # Required: no default. Boot fails when these are absent.
    django_secret_key: str
    database_url: PostgresDsn

    allowed_hosts: str = "*"
    cors_allowed_origins: str = ""
    body_max_bytes: int = 1_048_576

    # Kafka: reachable but never required for availability (invariant I9).
    kafka_bootstrap_servers: str = "localhost:9092"
    outbox_relay_enabled: bool = True

    # Internal endpoints (invariant I8).
    internal_token: str = ""

    # JWT (asymmetric). Empty by default; auth wiring lands in M2.
    jwt_signing_key: str = ""
    jwt_public_key: str = ""
    jwt_algorithm: str = "ES256"
    jwt_issuer: str = "job-service"

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> ServiceSettings:
    # pydantic-settings fills required fields from the environment/`.env`.
    return ServiceSettings()  # type: ignore[call-arg]
