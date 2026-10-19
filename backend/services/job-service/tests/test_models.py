"""Database-level guarantees for the M2 aggregates.

These tests assert real invariants (uniqueness, state validity, outbox
defaults), not implementation details.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import override_settings

from apps.jobs.models import EmploymentType, Job, JobStatus
from apps.outbox.models import OutboxEvent
from apps.recruiters.models import Recruiter

pytestmark = pytest.mark.django_db


def make_recruiter(email: str = "recruiter@example.com") -> Recruiter:
    return Recruiter.objects.create_user(
        email=email,
        password="correct horse battery staple",
        full_name="Ada Lovelace",
    )


def test_email_is_normalized_to_lowercase() -> None:
    recruiter = make_recruiter("Ada@Example.COM")
    recruiter.refresh_from_db()
    assert recruiter.email == "ada@example.com"


def test_duplicate_email_is_rejected_case_insensitively() -> None:
    make_recruiter("ada@example.com")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_recruiter("ADA@example.com")


@pytest.mark.django_db
@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"],
)
def test_password_is_argon2_hashed() -> None:
    recruiter = make_recruiter()
    assert recruiter.password.startswith("argon2$")
    assert recruiter.check_password("correct horse battery staple")


def test_new_job_defaults_to_draft_version_one() -> None:
    job = Job.objects.create(
        recruiter=make_recruiter(),
        title="Backend Engineer",
        description="Build things.",
        company="Example",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
    )
    assert job.status == JobStatus.DRAFT
    assert job.version == 1


def test_invalid_job_status_is_rejected_by_database() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Job.objects.create(
            recruiter=make_recruiter(),
            title="Backend Engineer",
            description="Build things.",
            company="Example",
            location="Remote",
            employment_type=EmploymentType.FULL_TIME,
            status="BOGUS",
        )


def test_invalid_employment_type_is_rejected_by_database() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Job.objects.create(
            recruiter=make_recruiter(),
            title="Backend Engineer",
            description="Build things.",
            company="Example",
            location="Remote",
            employment_type="BOGUS",
        )


def test_job_version_must_be_positive() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Job.objects.create(
            recruiter=make_recruiter(),
            title="Backend Engineer",
            description="Build things.",
            company="Example",
            location="Remote",
            employment_type=EmploymentType.FULL_TIME,
            version=0,
        )


def test_outbox_event_starts_unpublished() -> None:
    event = OutboxEvent.objects.create(
        aggregate_id="11111111-1111-1111-1111-111111111111",
        aggregate_version=1,
        event_type="job.created",
        payload={"hello": "world"},
    )
    assert event.published_at is None
    assert event.attempts == 0


def test_outbox_pending_index_is_partial() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s AND indexname = %s",
            ["outbox_events", "outbox_pending_idx"],
        )
        row = cursor.fetchone()
    assert row is not None, "expected the relay's pending index to exist"
    assert "WHERE (published_at IS NULL)" in row[0]
