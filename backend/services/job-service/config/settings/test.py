"""Test settings: fast hashing, no throttling, job_db test database."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgres://jobportal:jobportal@localhost:5433/job_db")

from config.settings.base import *

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"anon": "100000/min", "user": "1000000/min"},
}
