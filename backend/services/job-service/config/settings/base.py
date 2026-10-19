"""Shared Django settings for the Job Service.

Every value that can differ between environments is read from the environment
by ``config.env.ServiceSettings``. Environment-specific modules (``dev``,
``test``, ``prod``) import ``*`` from here.
"""

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
    "apps.recruiters",
    "apps.jobs",
    "apps.outbox",
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

# The recruiter is the Django auth user in this service.
AUTH_USER_MODEL = "recruiters.Recruiter"

# Request body limit (AGENTS.md section 2 hardening).
DATA_UPLOAD_MAX_MEMORY_SIZE = env.body_max_bytes

CORS_ALLOWED_ORIGINS = env.cors_allowed_origins_list
CORS_ALLOW_CREDENTIALS = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
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
        # Tighter bucket for credential endpoints (register/login).
        "auth": "10/min",
    },
    # Pagination default per AGENTS.md section 6 (page / pageSize).
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Job Service API",
    "DESCRIPTION": "Recruiters, jobs and the outbox. Owns job_db.",
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
    # base64-of-PEM env values are decoded here (newlines survive).
    "SIGNING_KEY": env.jwt_signing_key_pem,
    "VERIFYING_KEY": env.jwt_public_key_pem,
}

LOGGING = build_logging_config(env.log_level)
