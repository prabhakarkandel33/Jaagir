"""Base model helpers shared by the contract schemas.

The wire format uses camelCase keys. Python code uses snake_case. A single
CamelCase alias generator bridges the two; ``populate_by_name=True`` lets
Python callers use the Python names.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def to_camel(snake: str) -> str:
    head, *tail = snake.split("_")
    return head + "".join(word.capitalize() for word in tail)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware (use UTC)")
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc)]


class ContractModel(BaseModel):
    """Base for every contract schema: camelCase aliases, tolerant reader."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        str_strip_whitespace=True,
    )
