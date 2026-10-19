"""Job replica (ARCHITECTURE.md section 4.2).

This service NEVER writes job truth. Each row is built from Kafka events (and
reconciliation in M6) and updated only when the incoming version is higher.
``recruiter_id`` is a plain UUID, not a foreign key: the recruiter lives in the
Job Service database (invariant I1).
"""

from __future__ import annotations

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
    # Same id as the source job (the snapshot carries it).
    id = models.UUIDField(primary_key=True, editable=False)
    recruiter_id = models.UUIDField()

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

    status = models.CharField(max_length=20, choices=JobStatus.choices)
    version = models.PositiveIntegerField()

    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    # ``updated_at`` at the source (used by incremental reconciliation).
    source_updated_at = models.DateTimeField()
    # When this replica row was last written from an event/snapshot.
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs"
        indexes = [
            models.Index(
                fields=["status", "-published_at"],
                name="cjobs_status_published_idx",
            ),
            models.Index(
                fields=["recruiter_id", "-source_updated_at"],
                name="cjobs_recruiter_updated_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=JobStatus.values),
                name="cjobs_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(employment_type__in=EmploymentType.values),
                name="cjobs_employment_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="cjobs_version_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status} v{self.version})"
