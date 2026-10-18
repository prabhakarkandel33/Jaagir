"""The event envelope: the outer frame for every Kafka message."""

from __future__ import annotations

import json
from typing import Any, Final
from uuid import UUID

from pydantic import ValidationError

from contracts.base import ContractModel, UtcDatetime
from contracts.events import JobEventType, JobSnapshot

SCHEMA_VERSION: Final[int] = 1


class UnsupportedSchemaVersionError(ValueError):
    """Raised when a message carries a schemaVersion this service cannot read.

    This is a non-retryable error: the consumer must route the message to the
    DLQ instead of retrying it (ARCHITECTURE.md section 6.2).
    """


class EventEnvelope(ContractModel):
    event_id: UUID
    event_type: JobEventType
    schema_version: int = SCHEMA_VERSION
    aggregate_id: UUID
    aggregate_version: int
    occurred_at: UtcDatetime
    payload: JobSnapshot

    def to_json_bytes(self) -> bytes:
        return self.model_dump_json(by_alias=True).encode("utf-8")


def parse_envelope(raw: bytes | str | dict[str, Any]) -> EventEnvelope:
    """Parse and validate a raw Kafka message value.

    Raises:
        UnsupportedSchemaVersionError: the message has a future schemaVersion.
        ValidationError: the message does not match the contract.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        data: Any = json.loads(raw)
    else:
        data = raw

    if not isinstance(data, dict):
        raise ValidationError.from_exception_data(
            "EventEnvelope", [{"type": "dict_type", "loc": (), "input": data}]
        )

    version = data.get("schemaVersion", data.get("schema_version", SCHEMA_VERSION))
    if version != SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(f"unsupported schemaVersion: {version!r}")

    return EventEnvelope.model_validate(data)
