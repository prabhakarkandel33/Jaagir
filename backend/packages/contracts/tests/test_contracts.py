"""Unit tests for the shared event contract (valid and invalid samples)."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from contracts import (
    JOB_EVENT_TYPES,
    SCHEMA_VERSION,
    TOPIC_JOBS_EVENTS_V1,
    TOPIC_JOBS_EVENTS_V1_DLQ,
    parse_envelope,
)
from contracts.envelope import UnsupportedSchemaVersionError

VALID_ENVELOPE: dict = {
    "eventId": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
    "eventType": "JobPublished",
    "schemaVersion": 1,
    "aggregateId": "6b6f3b3a-2f5f-4a1e-9f1a-2c3d4e5f6a7b",
    "aggregateVersion": 7,
    "occurredAt": "2026-01-01T10:00:00.000Z",
    "payload": {
        "id": "6b6f3b3a-2f5f-4a1e-9f1a-2c3d4e5f6a7b",
        "recruiterId": "8c1d2e3f-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "title": "Senior Backend Engineer",
        "description": "Build reliable services.",
        "company": "Acme",
        "location": "Berlin",
        "employmentType": "FULL_TIME",
        "skills": ["python", "postgres", "kafka"],
        "status": "PUBLISHED",
        "version": 7,
        "publishedAt": "2026-01-01T09:00:00.000Z",
        "closedAt": None,
        "updatedAt": "2026-01-01T10:00:00.000Z",
    },
}


def test_topics_and_event_types_are_stable() -> None:
    assert TOPIC_JOBS_EVENTS_V1 == "jobs.events.v1"
    assert TOPIC_JOBS_EVENTS_V1_DLQ == "jobs.events.v1.dlq"
    assert JOB_EVENT_TYPES == ("JobPublished", "JobUpdated", "JobClosed")
    assert SCHEMA_VERSION == 1


def test_valid_envelope_parses_from_json_bytes() -> None:
    envelope = parse_envelope(json.dumps(VALID_ENVELOPE).encode("utf-8"))
    assert envelope.aggregate_version == 7
    assert envelope.payload.title == "Senior Backend Engineer"
    assert envelope.payload.skills == ["python", "postgres", "kafka"]
    assert envelope.event_type.value == "JobPublished"


def test_round_trip_uses_camel_case_wire_keys() -> None:
    envelope = parse_envelope(VALID_ENVELOPE)
    wire = json.loads(envelope.to_json_bytes())
    assert wire["eventId"] == VALID_ENVELOPE["eventId"]
    assert wire["aggregateVersion"] == 7
    assert wire["payload"]["employmentType"] == "FULL_TIME"
    assert wire["payload"]["recruiterId"] == VALID_ENVELOPE["payload"]["recruiterId"]


def test_unknown_schema_version_is_non_retryable() -> None:
    bad = deepcopy(VALID_ENVELOPE)
    bad["schemaVersion"] = 2
    with pytest.raises(UnsupportedSchemaVersionError):
        parse_envelope(bad)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e.pop("eventId"),
        lambda e: e.update({"aggregateVersion": "seven"}),
        lambda e: e["payload"].update({"employmentType": "NOPE"}),
        lambda e: e["payload"].update({"status": "ARCHIVED"}),
        lambda e: e["payload"].update({"id": "not-a-uuid"}),
        lambda e: e.update({"occurredAt": "2026-01-01T10:00:00"}),
    ],
)
def test_invalid_envelopes_are_rejected(mutate) -> None:
    bad = deepcopy(VALID_ENVELOPE)
    mutate(bad)
    with pytest.raises(ValidationError):
        parse_envelope(bad)


def test_non_object_payload_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_envelope(b'["not", "an", "object"]')
