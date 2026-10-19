"""Test settings: fast hashing, no throttling, candidate_db test database."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgres://jobportal:jobportal@localhost:5434/candidate_db")

from config.settings.base import *

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# No background consumer thread and no real broker during tests.
KAFKA_CONSUMER_ENABLED = False
INTERNAL_TOKEN = "test-internal-token"
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100000/min",
        "user": "1000000/min",
        "auth": "1000000/min",
    },
}


def _generate_es256_keypair() -> tuple[str, str]:
    """Ephemeral ES256 keypair so token tests do not need provisioned keys."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


# Candidate (this service) keypair, plus a separate Job Service keypair whose
# public key stands in for the recruiter-token verifier.
_TEST_SIGNING_KEY, _TEST_PUBLIC_KEY = _generate_es256_keypair()
_TEST_JOB_SIGNING_KEY, _TEST_JOB_PUBLIC_KEY = _generate_es256_keypair()
SIMPLE_JWT = {
    **SIMPLE_JWT,
    "SIGNING_KEY": _TEST_SIGNING_KEY,
    "VERIFYING_KEY": _TEST_PUBLIC_KEY,
}
JOB_SERVICE_JWT_PUBLIC_KEY = _TEST_JOB_PUBLIC_KEY
JOB_SERVICE_TEST_SIGNING_KEY = _TEST_JOB_SIGNING_KEY
