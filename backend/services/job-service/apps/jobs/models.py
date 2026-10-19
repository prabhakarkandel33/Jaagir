"""Job aggregate. Source of truth lives in the Job Service database."""

from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


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

    # Maintained by a BEFORE INSERT OR UPDATE trigger (migration 0002). A
    # GENERATED column is impossible here because array_to_string is only
    # STABLE (ARCHITECTURE.md section 7).
    search_vector = SearchVectorField(null=True, editable=False)

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
            # Partial GIN: only PUBLISHED rows are searchable, so the index is
            # smaller. The query must contain the literal predicate
            # `status = 'PUBLISHED'` or the planner cannot use it.
            GinIndex(
                fields=["search_vector"],
                condition=Q(status="PUBLISHED"),
                name="jobs_search_vector_gin",
            ),
            GinIndex(fields=["skills"], name="jobs_skills_gin"),
            # Browse (empty query) and stable tie-breaking.
            models.Index(
                fields=["-published_at", "id"],
                condition=Q(status="PUBLISHED"),
                name="jobs_pub_browse_idx",
            ),
            models.Index(fields=["employment_type"], name="jobs_employment_idx"),
            models.Index(Lower("location"), name="jobs_location_lower_idx"),
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
