#!/usr/bin/env python
"""Django management entry point for the Candidate Service."""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Could not import Django. Run this with `uv run python manage.py ...`."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
