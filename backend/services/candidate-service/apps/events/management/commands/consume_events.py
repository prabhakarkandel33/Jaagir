"""``manage.py consume_events`` -- the replica consumer loop (section 6.2).

A separate container/process. It keeps running while Kafka is down and resumes
from the committed offset once the broker returns (invariant I9).
"""

from __future__ import annotations

import contextlib
import logging
import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.events.consumer import get_event_consumer

logger = logging.getLogger("apps.events.consumer")


class Command(BaseCommand):
    help = "Consume job events and maintain the local job replica."

    def handle(self, *args: object, **options: object) -> None:
        if not settings.KAFKA_CONSUMER_ENABLED:
            self.stdout.write("KAFKA_CONSUMER_ENABLED is false; consumer not started")
            return

        consumer = get_event_consumer()
        stop = threading.Event()

        def _shutdown(signum: int, frame: object) -> None:
            logger.info(
                "consumer shutdown requested", extra={"component": "consumer", "signal": signum}
            )
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            # Not the main thread / signal unsupported on this platform.
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, _shutdown)

        self.stdout.write(f"consumer started (group={settings.KAFKA_CONSUMER_GROUP_ID})")
        try:
            consumer.run(stop)
        finally:
            self.stdout.write("consumer stopped")
