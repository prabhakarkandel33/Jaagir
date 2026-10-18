"""Event payload schemas.

Every job event carries the FULL job snapshot (not a diff). This makes the
consumer a simple version-guarded upsert that is safe under loss, duplication
and reordering, and lets reconciliation reuse the same upsert
(ARCHITECTURE.md section 5).
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from contracts.base import ContractModel, UtcDatetime


class JobStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"


class EmploymentType(StrEnum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERNSHIP = "INTERNSHIP"
    TEMPORARY = "TEMPORARY"


class ApplicationStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"


class JobEventType(StrEnum):
    JOB_PUBLISHED = "JobPublished"
    JOB_UPDATED = "JobUpdated"
    JOB_CLOSED = "JobClosed"


class JobSnapshot(ContractModel):
    """Full state of a job, as published on the wire."""

    id: UUID
    recruiter_id: UUID
    title: str
    description: str
    company: str
    location: str
    employment_type: EmploymentType
    skills: list[str] = Field(default_factory=list)
    status: JobStatus
    version: int
    published_at: UtcDatetime | None = None
    closed_at: UtcDatetime | None = None
    updated_at: UtcDatetime
