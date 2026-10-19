#!/usr/bin/env python
"""Capture EXPLAIN (ANALYZE, BUFFERS) plans for the search queries (M5).

Runs three representative queries against one service database twice:

  * baseline: the partial GIN index is disabled, so PostgreSQL must scan;
  * indexed:  the normal plan, which should use the GIN index.

Output is Markdown-ish plain text on stdout; capture it into
docs/search-performance.md.

Usage (from the repo root, after seeding):
    uv run --project backend python scripts/explain_analyze.py --service job
    uv run --project backend python scripts/explain_analyze.py --service candidate
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SERVICES = {
    "job": "backend/services/job-service",
    "candidate": "backend/services/candidate-service",
}

QUERIES: list[tuple[str, str, dict[str, object]]] = [
    (
        "Q1 title/description keyword",
        """
        SELECT id, title, ts_rank_cd(search_vector, q) AS rank
        FROM jobs, websearch_to_tsquery('english', %(q)s) AS q
        WHERE status = 'PUBLISHED' AND search_vector @@ q
        ORDER BY rank DESC, published_at DESC NULLS LAST, id
        LIMIT 20 OFFSET 0
        """,
        {"q": "python engineer"},
    ),
    (
        "Q2 keyword + employment type filter",
        """
        SELECT id, title, ts_rank_cd(search_vector, q) AS rank
        FROM jobs, websearch_to_tsquery('english', %(q)s) AS q
        WHERE status = 'PUBLISHED' AND search_vector @@ q
          AND employment_type = %(employment_type)s
        ORDER BY rank DESC, published_at DESC NULLS LAST, id
        LIMIT 20 OFFSET 0
        """,
        {"q": "kubernetes", "employment_type": "CONTRACT"},
    ),
    (
        "Q3 skills containment filter",
        """
        SELECT id, title
        FROM jobs
        WHERE status = 'PUBLISHED' AND skills @> %(skills)s
        ORDER BY published_at DESC NULLS LAST, id
        LIMIT 20 OFFSET 0
        """,
        {"skills": ["python", "django"]},
    ),
]


def run(service: str) -> None:
    os.chdir(Path(__file__).resolve().parent.parent / SERVICES[service])
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    sys.path.insert(0, os.getcwd())

    import django

    django.setup()

    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*), count(*) FILTER (WHERE status='PUBLISHED') FROM jobs")
        total, published = cursor.fetchone()
        cursor.execute("SELECT pg_size_pretty(pg_total_relation_size('jobs'))")
        size = cursor.fetchone()[0]

    print(f"# EXPLAIN ANALYZE -- {service}-service")
    print()
    print(f"rows: {total} (PUBLISHED {published}); table+indexes: {size}")
    print()

    for label, sql, params in QUERIES:
        for mode in ("baseline (seq scan)", "indexed"):
            with connection.cursor() as cursor:
                # SET LOCAL is a no-op outside a transaction block, so use
                # session-level SET and reset it explicitly afterwards.
                if mode.startswith("baseline"):
                    cursor.execute("SET enable_indexscan = off")
                    cursor.execute("SET enable_bitmapscan = off")
                    cursor.execute("SET enable_indexonlyscan = off")
                else:
                    cursor.execute("SET enable_indexscan = on")
                    cursor.execute("SET enable_bitmapscan = on")
                    cursor.execute("SET enable_indexonlyscan = on")
                cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
                plan = "\n".join(row[0] for row in cursor.fetchall())
                cursor.execute("RESET enable_indexscan")
                cursor.execute("RESET enable_bitmapscan")
                cursor.execute("RESET enable_indexonlyscan")
            print(f"## {label} -- {mode}")
            print("```")
            print(plan)
            print("```")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture EXPLAIN plans for search.")
    parser.add_argument("--service", choices=sorted(SERVICES), default="job")
    args = parser.parse_args()
    run(args.service)


if __name__ == "__main__":
    main()
