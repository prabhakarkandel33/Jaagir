"""Candidate account model (ARCHITECTURE.md section 4.2).

The candidate IS the Django auth user (``AUTH_USER_MODEL``): email login,
argon2id password hashing, UUID primary key. Mirrors the recruiter model in the
Job Service so SimpleJWT and the framework's password machinery work without a
separate profile table.
"""

from __future__ import annotations

from uuid import uuid4

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.functions import Lower


def resume_upload_path(instance: Candidate, filename: str) -> str:
    """Random stored name: a resume can never be fetched by guessing a path."""
    del instance, filename
    return f"resumes/{uuid4().hex}.pdf"


class CandidateManager(BaseUserManager["Candidate"]):
    use_in_migrations = True

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> Candidate:
        if not email:
            raise ValueError("email is required")
        email = self.normalize_email(email).lower()
        candidate = self.model(email=email, **extra_fields)
        candidate.set_password(password)
        candidate.save(using=self._db)
        return candidate

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> Candidate:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class Candidate(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    # ``unique=True`` is required by Django for a USERNAME_FIELD. The
    # functional lower(email) constraint below is the case-insensitive guard.
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, blank=True, default="")
    headline = models.CharField(max_length=200, blank=True, default="")
    location = models.CharField(max_length=200, blank=True, default="")
    skills = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
    )
    summary = models.TextField(blank=True, default="")
    # Optional external resume link plus an optional uploaded PDF (M7A
    # exception to ARCHITECTURE.md section 13). Media is never served directly.
    resume_url = models.URLField(max_length=500, blank=True, default="")
    resume_file = models.FileField(
        upload_to=resume_upload_path,
        max_length=255,
        blank=True,
        default="",
    )
    resume_filename = models.CharField(max_length=255, blank=True, default="")
    resume_uploaded_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CandidateManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "candidates"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="candidates_email_lower_uniq",
            ),
        ]

    def __str__(self) -> str:
        return self.email
