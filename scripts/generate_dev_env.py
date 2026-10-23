"""Create the local service `.env` files when they are absent.

This script is for local development and CI only. It never overwrites an
existing `.env` file. Generated keys are ephemeral and must not be reused in
production.
"""

from __future__ import annotations

import base64
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parent.parent
JOB_ENV = ROOT / "backend" / "services" / "job-service" / ".env"
CANDIDATE_ENV = ROOT / "backend" / "services" / "candidate-service" / ".env"


def _keypair() -> tuple[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return (
        base64.b64encode(private_pem).decode(),
        base64.b64encode(public_pem).decode(),
    )


def _write(path: Path, values: dict[str, str]) -> None:
    text = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(0o600)


def main() -> int:
    if JOB_ENV.exists() and CANDIDATE_ENV.exists():
        print("Using the existing service .env files.")
        return 0
    if JOB_ENV.exists() or CANDIDATE_ENV.exists():
        print(
            "Only one service .env exists. Remove both files to regenerate a "
            "matching pair, or restore the missing file.",
            file=sys.stderr,
        )
        return 2

    job_private, job_public = _keypair()
    candidate_private, candidate_public = _keypair()
    internal_token = secrets.token_urlsafe(32)
    admin_password = secrets.token_urlsafe(24)
    django_secret = secrets.token_urlsafe(48)

    common = {
        "DEBUG": "true",
        "LOG_LEVEL": "INFO",
        "ALLOWED_HOSTS": "*",
        "CORS_ALLOWED_ORIGINS": "http://localhost:5174",
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
        "INTERNAL_TOKEN": internal_token,
        "JWT_ALGORITHM": "ES256",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": admin_password,
    }

    _write(
        JOB_ENV,
        {
            "DJANGO_SECRET_KEY": django_secret,
            **common,
            "DATABASE_URL": "postgresql://jobportal:jobportal@localhost:5433/job_db",
            "OUTBOX_RELAY_ENABLED": "true",
            "JWT_ISSUER": "job-service",
            "JWT_SIGNING_KEY": job_private,
            "JWT_PUBLIC_KEY": job_public,
        },
    )
    _write(
        CANDIDATE_ENV,
        {
            "DJANGO_SECRET_KEY": django_secret,
            **common,
            "DATABASE_URL": "postgresql://jobportal:jobportal@localhost:5434/candidate_db",
            "KAFKA_CONSUMER_GROUP_ID": "candidate-service",
            "KAFKA_CONSUMER_ENABLED": "true",
            "MEDIA_ROOT": "",
            "RESUME_MAX_BYTES": "5242880",
            "RECONCILE_ENABLED": "true",
            "RECONCILE_INCREMENTAL_SECONDS": "300",
            "RECONCILE_BATCH_LIMIT": "500",
            "JOB_SERVICE_INTERNAL_URL": "http://localhost:3001",
            "JWT_ISSUER": "candidate-service",
            "JWT_SIGNING_KEY": candidate_private,
            "JWT_PUBLIC_KEY": candidate_public,
            "JOB_SERVICE_JWT_PUBLIC_KEY": job_public,
        },
    )
    print("Created local service .env files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
