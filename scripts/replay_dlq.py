#!/usr/bin/env python
"""Replay the Kafka DLQ through the Candidate Service admin endpoint.

    uv run --project backend python scripts/replay_dlq.py --dry-run --limit 10
    uv run --project backend python scripts/replay_dlq.py --limit 100

The endpoint is the ONLY implementation of replay (no second Kafka client in
this script), so the CLI and the server cannot drift. The internal token is
read from `backend/services/candidate-service/.env` unless `--token` is given.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = ROOT / "backend" / "services" / "candidate-service" / ".env"


def read_token(env_file: Path) -> str:
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("INTERNAL_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"INTERNAL_TOKEN not found in {env_file}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:3002")
    parser.add_argument("--token", default=None)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = args.token or read_token(Path(args.env_file))
    query = f"limit={args.limit}" + ("&dryRun=true" if args.dry_run else "")
    request = urllib.request.Request(
        f"{args.url.rstrip('/')}/internal/admin/dlq/replay?{query}",
        headers={"X-Internal-Token": token, "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        print(f"replay failed: HTTP {exc.code} {exc.read().decode()}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"replay failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"dryRun={body['dryRun']} read={body['read']} published={body['published']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
