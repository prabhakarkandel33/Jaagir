"""Shared Django settings for the Candidate Service."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from config.db import database_config
from config.env import get_settings
from config.logging import build_logging_config

env = get_settings()

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = env.django_secret_key
DEBUG = env.debug
ALLOWED_HOSTS = env.allowed_hosts_list

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "apps.core",
    "apps.candidates",
    "apps.jobs",
    "apps.applications",
    "apps.events",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "config.middleware.RequestIdMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# drf-spectacular's Swagger UI is a Django template; templates must be enabled.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

DATABASES = {"default": database_config(env.database_url)}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS: list[dict] = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The candidate is the Django auth user in this service.
AUTH_USER_MODEL = "candidates.Candidate"

DATA_UPLOAD_MAX_MEMORY_SIZE = env.body_max_bytes

CORS_ALLOWED_ORIGINS = env.cors_allowed_origins_list
CORS_ALLOW_CREDENTIALS = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Issuer-aware: accepts candidate tokens (this service's key) and
        # recruiter tokens (the Job Service public key from env).
        "apps.core.authentication.IssuerAwareJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "600/min",
        "auth": "10/min",
    },
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Candidate & Application Service API",
    "DESCRIPTION": "Candidates, applications and the job replica.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/",
}

SIMPLE_JWT = {
    "ALGORITHM": env.jwt_algorithm,
    "ISSUER": env.jwt_issuer,
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    # ARCHITECTURE.md section 9: the subject claim is ``sub``.
    "USER_ID_CLAIM": "sub",
    # This service signs candidate tokens (base64-of-PEM env values decoded
    # here so newlines survive).
    "SIGNING_KEY": env.jwt_signing_key_pem,
    "VERIFYING_KEY": env.jwt_public_key_pem,
}

# Recruiter tokens are issued by the Job Service; verify them with the peer's
# public key only (ARCHITECTURE.md section 9).
JOB_SERVICE_JWT_ISSUER = "job-service"
JOB_SERVICE_JWT_PUBLIC_KEY = env.job_service_jwt_public_key_pem

LOGGING = build_logging_config(env.log_level)

# Kafka (invariant I9: never required for availability).
KAFKA_BOOTSTRAP_SERVERS = env.kafka_bootstrap_servers
KAFKA_CONSUMER_GROUP_ID = env.kafka_consumer_group_id
KAFKA_CONSUMER_ENABLED = env.kafka_consumer_enabled
KAFKA_MESSAGE_TIMEOUT_MS = env.kafka_message_timeout_ms

# Reconciliation (M6).
RECONCILE_ENABLED = env.reconcile_enabled
RECONCILE_INCREMENTAL_SECONDS = env.reconcile_incremental_seconds
RECONCILE_FULL_SECONDS = env.reconcile_full_seconds
RECONCILE_STARTUP_DELAY_SECONDS = env.reconcile_startup_delay_seconds
RECONCILE_BATCH_LIMIT = env.reconcile_batch_limit
RECONCILE_HTTP_TIMEOUT_SECONDS = env.reconcile_http_timeout_seconds

# Internal endpoints + the Job Service internal URL (invariant I8).
INTERNAL_TOKEN = env.internal_token
JOB_SERVICE_INTERNAL_URL = env.job_service_internal_url

# Admin site (frontend `/admin`). Credentials live in `.env`, never in the bundle.
ADMIN_USERNAME = env.admin_username
ADMIN_PASSWORD = env.admin_password
