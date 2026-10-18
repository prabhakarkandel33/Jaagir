"""Topic names and event-type constants. Contract only, no side effects."""

from __future__ import annotations

from typing import Final

TOPIC_JOBS_EVENTS_V1: Final[str] = "jobs.events.v1"
TOPIC_JOBS_EVENTS_V1_DLQ: Final[str] = "jobs.events.v1.dlq"

# Kafka headers carried on every event (ARCHITECTURE.md section 5).
HEADER_EVENT_TYPE: Final[str] = "event-type"
HEADER_EVENT_ID: Final[str] = "event-id"
HEADER_SCHEMA_VERSION: Final[str] = "schema-version"

# DLQ-only headers.
HEADER_DLQ_ERROR: Final[str] = "dlq-error"
HEADER_DLQ_ATTEMPTS: Final[str] = "dlq-attempts"
HEADER_DLQ_SOURCE_TOPIC: Final[str] = "dlq-source-topic"
HEADER_DLQ_SOURCE_PARTITION: Final[str] = "dlq-source-partition"
HEADER_DLQ_SOURCE_OFFSET: Final[str] = "dlq-source-offset"
HEADER_DLQ_FAILED_AT: Final[str] = "dlq-failed-at"

JOB_EVENT_TYPES: Final[tuple[str, ...]] = (
    "JobPublished",
    "JobUpdated",
    "JobClosed",
)
