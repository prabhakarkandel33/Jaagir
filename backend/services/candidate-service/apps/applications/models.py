"""Application aggregate (ARCHITECTURE.md section 4.2).

"One application per candidate per job" is enforced by a database UNIQUE
constraint (invariant I7); the service maps SQLSTATE 23505 to HTTP 409 instead
of checking-then-inserting (no race).
"""

from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.db import models


class ApplicationStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"


class Application(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    # FK to the local replica row; the replica only holds non-draft jobs.
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.PROTECT,
        related_name="applications",
    )

    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.SUBMITTED,
    )
    cover_letter = models.TextField(blank=True, default="")
    # Snapshot so history stays readable even if the replica changes later.
    job_title_snapshot = models.CharField(max_length=200)
    company_snapshot = models.CharField(max_length=200)

    applied_at = models.DateTimeField(auto_now_add=True)
    status_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "applications"
        indexes = [
            models.Index(
                fields=["candidate", "-applied_at"],
                name="apps_candidate_applied_idx",
            ),
            models.Index(
                fields=["job", "-applied_at"],
                name="apps_job_applied_idx",
            ),
        ]
        constraints = [
            # Invariant I7: the database is the single source of truth here.
            models.UniqueConstraint(
                fields=["candidate", "job"],
                name="applications_candidate_job_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ApplicationStatus.values),
                name="applications_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.candidate_id} -> {self.job_id} ({self.status})"
