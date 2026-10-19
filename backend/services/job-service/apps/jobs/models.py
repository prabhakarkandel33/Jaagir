"""Job aggregate. Source of truth lives in the Job Service database."""

from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


class JobStatus(models.TextChoices):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"


class EmploymentType(models.TextChoices):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERNSHIP = "INTERNSHIP"
    TEMPORARY = "TEMPORARY"


class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="jobs",
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    skills = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.DRAFT,
    )
    # Bumped on EVERY write. Version gaps are expected and harmless: draft
    # edits bump the version but emit no event (ARCHITECTURE.md section 4.1).
    version = models.PositiveIntegerField(default=1)

    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs"
        indexes = [
            models.Index(
                fields=["recruiter", "-created_at"],
                name="jobs_recruiter_created_idx",
            ),
            models.Index(
                fields=["status", "-published_at"],
                name="jobs_status_published_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=JobStatus.values),
                name="jobs_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(employment_type__in=EmploymentType.values),
                name="jobs_employment_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="jobs_version_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"
