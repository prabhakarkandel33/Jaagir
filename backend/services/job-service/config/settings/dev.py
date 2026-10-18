"""Development settings: dev defaults for env vars, permissive CORS."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "dev-insecure-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "postgres://jobportal:jobportal@localhost:5433/job_db")

from config.settings.base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
