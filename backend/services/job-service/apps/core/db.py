"""Transaction helper.

``with_tx`` runs a callable inside one database transaction. State changes and
their outbox rows MUST share this transaction (invariant I2): if the callable
raises, both the change and the outbox row roll back together.
"""

from __future__ import annotations

from collections.abc import Callable

from django.db import transaction


def with_tx[T](fn: Callable[[], T]) -> T:
    with transaction.atomic():
        return fn()
