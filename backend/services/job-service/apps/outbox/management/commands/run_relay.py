"""``manage.py run_relay`` — the outbox relay loop (ARCHITECTURE.md section 6.1).

A separate container/process. It keeps running when Kafka is down: rows stay
pending with capped backoff and drain automatically once the broker returns.
"""

from __future__ import annotations

import logging
import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.kafka import KafkaClient, get_kafka_client
from apps.outbox import relay

logger = logging.getLogger("apps.outbox.relay")

POLL_INTERVAL_S = 0.5
RECONNECT_INTERVAL_S = 10.0


class Command(BaseCommand):
    help = "Run the transactional-outbox relay loop (producer side)."

    def handle(self, *args: object, **options: object) -> None:
        if not settings.OUTBOX_RELAY_ENABLED:
            self.stdout.write("outbox relay disabled (OUTBOX_RELAY_ENABLED=false)")
            return

        stop = threading.Event()

        def _stop(signum: int, _frame: object) -> None:
            self.stdout.write(f"received signal {signum}; stopping after this cycle")
            stop.set()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        client: KafkaClient = get_kafka_client()
        # The monitor owns connect + topic creation and keeps `client.status`
        # current (it pings every RECONNECT_INTERVAL_S). The relay loop only
        # publishes while the status is "up", so a broker outage leaves rows
        # pending instead of burning a flush timeout per row.
        client.start_monitor(interval_s=RECONNECT_INTERVAL_S)
        self.stdout.write(f"outbox relay started (bootstrap={settings.KAFKA_BOOTSTRAP_SERVERS})")

        while not stop.is_set():
            if client.status != "up":
                stop.wait(POLL_INTERVAL_S)
                continue

            try:
                result = relay.relay_once(client)
            except Exception as exc:  # never let the loop die
                logger.exception("relay cycle crashed")
                self.stderr.write(f"relay cycle crashed: {exc}")
                result = None

            if result is not None and result.error:
                # Backoff already recorded; pause a little before retrying.
                stop.wait(min(relay.BACKOFF_CAP_SECONDS, 2.0))
            else:
                stop.wait(POLL_INTERVAL_S)

        client.stop_monitor()
        self.stdout.write("outbox relay stopped")
