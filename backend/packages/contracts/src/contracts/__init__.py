"""Shared Kafka event contract for the Job Portal.

This package holds ONLY the wire contract: the event envelope, the job
snapshot payload, the event-type constants and the topic names. It has no
runtime logic, no database access and no HTTP. See ARCHITECTURE.md section 5.
"""

from contracts.envelope import SCHEMA_VERSION, EventEnvelope, parse_envelope
from contracts.events import (
    ApplicationStatus,
    EmploymentType,
    JobEventType,
    JobSnapshot,
    JobStatus,
)
from contracts.topics import (
    HEADER_DLQ_ATTEMPTS,
    HEADER_DLQ_ERROR,
    HEADER_DLQ_FAILED_AT,
    HEADER_DLQ_SOURCE_OFFSET,
    HEADER_DLQ_SOURCE_PARTITION,
    HEADER_DLQ_SOURCE_TOPIC,
    HEADER_EVENT_ID,
    HEADER_EVENT_TYPE,
    HEADER_SCHEMA_VERSION,
    JOB_EVENT_TYPES,
    TOPIC_JOBS_EVENTS_V1,
    TOPIC_JOBS_EVENTS_V1_DLQ,
)

__all__ = [
    "HEADER_DLQ_ATTEMPTS",
    "HEADER_DLQ_ERROR",
    "HEADER_DLQ_FAILED_AT",
    "HEADER_DLQ_SOURCE_OFFSET",
    "HEADER_DLQ_SOURCE_PARTITION",
    "HEADER_DLQ_SOURCE_TOPIC",
    "HEADER_EVENT_ID",
    "HEADER_EVENT_TYPE",
    "HEADER_SCHEMA_VERSION",
    "JOB_EVENT_TYPES",
    "SCHEMA_VERSION",
    "TOPIC_JOBS_EVENTS_V1",
    "TOPIC_JOBS_EVENTS_V1_DLQ",
    "ApplicationStatus",
    "EmploymentType",
    "EventEnvelope",
    "JobEventType",
    "JobSnapshot",
    "JobStatus",
    "parse_envelope",
]
