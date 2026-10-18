"""Fail-fast environment configuration for the Candidate Service."""

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

    service_name: str = "candidate-service"
    debug: bool = False
    log_level: str = "INFO"

    # Required: no default. Boot fails when these are absent.
    django_secret_key: str
    database_url: PostgresDsn

    allowed_hosts: str = "*"
    cors_allowed_origins: str = ""
    body_max_bytes: int = 1_048_576

    # Kafka: consumer settings. Kafka is optional for availability (I9).
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group_id: str = "candidate-service"

    # Reconciliation (M6).
    reconcile_incremental_seconds: int = 300
    reconcile_batch_limit: int = 500

    # Internal endpoints + talking to the Job Service internally (I8).
    internal_token: str = ""
    job_service_internal_url: str = "http://localhost:3001"

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


@lru_cache
def get_settings() -> ServiceSettings:
    # pydantic-settings fills required fields from the environment/`.env`.
    return ServiceSettings()  # type: ignore[call-arg]
