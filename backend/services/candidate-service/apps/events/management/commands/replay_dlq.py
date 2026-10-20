"""``manage.py replay_dlq [--dry-run] [--limit N]`` -- DLQ replay (section 6.2)."""

from __future__ import annotations

from typing import cast

from django.core.management.base import BaseCommand

from apps.events.dlq import DEFAULT_LIMIT, replay_dlq


class Command(BaseCommand):
    help = "Re-publish messages from jobs.events.v1.dlq to jobs.events.v1."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")  # type: ignore[attr-defined]
        parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)  # type: ignore[attr-defined]

    def handle(self, *args: object, **options: object) -> None:
        result = replay_dlq(
            limit=cast(int, options["limit"]),
            dry_run=bool(options["dry_run"]),
        )
        self.stdout.write(f"dlq replay read={result['read']} published={result['published']}")
