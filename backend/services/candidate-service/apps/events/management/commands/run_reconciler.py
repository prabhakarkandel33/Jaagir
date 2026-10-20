"""``manage.py run_reconciler`` -- the replica reconciler loop (section 6.3).

Schedule:

- one FULL pass ``RECONCILE_STARTUP_DELAY_SECONDS`` after boot,
- an INCREMENTAL pass every ``RECONCILE_INCREMENTAL_SECONDS``,
- a FULL pass every ``RECONCILE_FULL_SECONDS`` (nightly at the default 24 h).

A failed pass (for example the Job Service is down) never stops the loop: the
error is recorded in ``reconcile_runs`` and the next cycle tries again.
"""

from __future__ import annotations

import contextlib
import logging
import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.events.reconciler import MODE_FULL, MODE_INCREMENTAL, reconcile

logger = logging.getLogger("apps.events.reconciler")


class Command(BaseCommand):
    help = "Reconcile the job replica against the Job Service snapshot API."

    def handle(self, *args: object, **options: object) -> None:
        if not settings.RECONCILE_ENABLED:
            self.stdout.write("RECONCILE_ENABLED is false; reconciler not started")
            return

        stop = threading.Event()

        def _shutdown(signum: int, frame: object) -> None:
            logger.info("reconciler shutdown requested", extra={"component": "reconciler"})
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, _shutdown)

        self.stdout.write(
            "reconciler started "
            f"(startup={settings.RECONCILE_STARTUP_DELAY_SECONDS}s, "
            f"incremental={settings.RECONCILE_INCREMENTAL_SECONDS}s, "
            f"full={settings.RECONCILE_FULL_SECONDS}s)"
        )

        next_full_at = float(settings.RECONCILE_STARTUP_DELAY_SECONDS)
        next_incremental_at = float(settings.RECONCILE_STARTUP_DELAY_SECONDS)
        elapsed = 0.0
        tick = 1.0
        while not stop.wait(tick):
            elapsed += tick
            if elapsed >= next_full_at:
                self._run(MODE_FULL)
                next_full_at = elapsed + settings.RECONCILE_FULL_SECONDS
                # A full pass covers the incremental window too.
                next_incremental_at = min(
                    next_incremental_at + settings.RECONCILE_INCREMENTAL_SECONDS,
                    next_full_at,
                )
                continue
            if elapsed >= next_incremental_at:
                self._run(MODE_INCREMENTAL)
                next_incremental_at = elapsed + settings.RECONCILE_INCREMENTAL_SECONDS

        self.stdout.write("reconciler stopped")

    def _run(self, mode: str) -> None:
        try:
            run = reconcile(mode)
        except Exception as exc:
            self.stderr.write(f"reconcile ({mode}) failed: {exc}")
            return
        self.stdout.write(f"reconcile ({mode}) checked={run.checked} repaired={run.repaired}")
