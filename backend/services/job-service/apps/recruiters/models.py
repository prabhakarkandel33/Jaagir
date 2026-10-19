"""Recruiter account model.

The recruiter IS the Django auth user (``AUTH_USER_MODEL``): email login,
argon2id password hashing, UUID primary key. This keeps SimpleJWT and the
framework's password machinery working without a separate profile table.
"""

from __future__ import annotations

from uuid import uuid4

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class RecruiterManager(BaseUserManager["Recruiter"]):
    use_in_migrations = True

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> Recruiter:
        if not email:
            raise ValueError("email is required")
        email = self.normalize_email(email).lower()
        recruiter = self.model(email=email, **extra_fields)
        recruiter.set_password(password)
        recruiter.save(using=self._db)
        return recruiter

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> Recruiter:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class Recruiter(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    # ``unique=True`` is required by Django for a USERNAME_FIELD. The
    # functional lower(email) constraint below is the case-insensitive guard.
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200)
    company_name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RecruiterManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "recruiters"
        constraints = [
            # Prefer a functional unique constraint over citext (no extension
            # privileges needed for the app role).
            models.UniqueConstraint(
                Lower("email"),
                name="recruiters_email_lower_uniq",
            ),
        ]

    def __str__(self) -> str:
        return self.email
