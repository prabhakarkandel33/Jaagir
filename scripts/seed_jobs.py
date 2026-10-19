#!/usr/bin/env python
"""Seed jobs for the M5 search benchmark (100k rows by default).

Runs inside the workspace so it reuses the service settings and the real
trigger. Two modes:

  * job-service (source of truth): also creates a few recruiters, because
    ``jobs.recruiter_id`` is a foreign key there.
  * candidate-service (replica): inserts directly. Allowed for benchmark
    seeding only, and only inside ``scripts/`` (M5 note in CONTEXT.md).

Usage (from the repo root):
    uv run --project backend python scripts/seed_jobs.py --service job --count 100000
    uv run --project backend python scripts/seed_jobs.py --service candidate --count 100000

Both modes use one COPY per batch, so 100k rows take seconds, not minutes.
The trigger fires per row, exactly as it does for real writes.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

SERVICES = {
    "job": ("backend/services/job-service", "job_db"),
    "candidate": ("backend/services/candidate-service", "candidate_db"),
}

ADJECTIVES = [
    "Senior", "Junior", "Lead", "Staff", "Principal", "Associate", "Head of",
    "Freelance", "Remote", "Hybrid", "Global", "Regional", "Interim", "Seasonal",
]
ROLES = [
    "Backend Engineer", "Frontend Engineer", "Full Stack Developer", "Data Engineer",
    "Data Scientist", "DevOps Engineer", "Site Reliability Engineer", "Platform Engineer",
    "Machine Learning Engineer", "Security Engineer", "QA Engineer", "Product Manager",
    "Product Designer", "Engineering Manager", "Solutions Architect", "Cloud Architect",
    "Database Administrator", "Mobile Developer", "iOS Developer", "Android Developer",
    "Technical Writer", "Support Engineer", "Systems Analyst", "Business Analyst",
]
SKILLS = [
    "python", "django", "flask", "fastapi", "javascript", "typescript", "react", "vue",
    "angular", "node", "go", "rust", "java", "kotlin", "scala", "csharp", "ruby",
    "rails", "php", "laravel", "sql", "postgres", "mysql", "mongodb", "redis",
    "kafka", "rabbitmq", "docker", "kubernetes", "terraform", "ansible", "aws",
    "gcp", "azure", "linux", "git", "graphql", "grpc", "rest", "elasticsearch",
    "spark", "airflow", "dbt", "pandas", "numpy", "pytorch", "tensorflow", "pytest",
    "celery", "nginx", "caddy", "prometheus", "grafana", "jenkins", "github-actions",
]
COMPANIES = [
    "Acme", "Globex", "Initech", "Umbrella", "Hooli", "Stark Industries", "Wayne Corp",
    "Cyberdyne", "Soylent", "Wonka Labs", "Tyrell", "Massive Dynamic", "Aperture",
    "Black Mesa", "Nakatomi", "Gringotts", "Duff Beer", "Vandelay", "Pied Piper",
    "Monarch", "Blue Sun", "Rekall", "Weiland-Yutani", "Oscorp", "Prestige Worldwide",
]
LOCATIONS = [
    "Berlin", "London", "Paris", "Amsterdam", "Dublin", "Madrid", "Lisbon", "Warsaw",
    "Prague", "Vienna", "Zurich", "Stockholm", "Oslo", "Copenhagen", "Helsinki",
    "New York", "San Francisco", "Austin", "Seattle", "Boston", "Toronto", "Vancouver",
    "Bengaluru", "Mumbai", "Pune", "Hyderabad", "Singapore", "Sydney", "Tokyo", "Remote",
]
EMPLOYMENT = ["FULL_TIME", "PART_TIME", "CONTRACT", "INTERNSHIP", "TEMPORARY"]
BENEFITS = [
    "health insurance", "remote work", "stock options", "learning budget", "paid time off",
    "parental leave", "flexible hours", "annual bonus", "home office stipend", "pension",
    "gym membership", "conference budget", "sabbatical", "four-day week",
]
RESPONSIBILITIES = [
    "design and build services", "review code", "mentor teammates", "own production systems",
    "improve observability", "write technical documentation", "drive architecture decisions",
    "collaborate with product", "optimize database queries", "automate deployments",
    "triage incidents", "maintain CI pipelines", "profile performance",
]


def _sentence(rng: random.Random) -> str:
    return f"We are looking for someone to {rng.choice(RESPONSIBILITIES)} and {rng.choice(RESPONSIBILITIES)}."


def make_row(rng: random.Random, recruiter_ids: list[str], index: int) -> dict[str, object]:
    roll = rng.random()
    if roll < 0.90:
        status = "PUBLISHED"
    elif roll < 0.95:
        status = "CLOSED"
    else:
        status = "DRAFT"

    now = datetime.now(UTC)
    created = now - timedelta(days=rng.randint(0, 900), seconds=rng.randint(0, 86_399))
    published = created + timedelta(hours=rng.randint(1, 72)) if status != "DRAFT" else None
    closed = published + timedelta(days=rng.randint(1, 180)) if status == "CLOSED" and published else None
    updated = closed or published or created

    title = f"{rng.choice(ADJECTIVES)} {rng.choice(ROLES)}"
    skills = rng.sample(SKILLS, k=rng.randint(2, 8))
    description = " ".join(
        [
            _sentence(rng),
            "You will work with " + ", ".join(skills) + ".",
            _sentence(rng),
            "We offer " + ", ".join(rng.sample(BENEFITS, k=3)) + ".",
        ]
    )
    return {
        "id": str(uuid.uuid4()),
        "recruiter_id": rng.choice(recruiter_ids),
        "title": title,
        "description": description,
        "company": rng.choice(COMPANIES),
        "location": rng.choice(LOCATIONS),
        "employment_type": rng.choice(EMPLOYMENT),
        "skills": "{" + ",".join(skills) + "}",
        "status": status,
        "version": rng.randint(1, 9),
        "published_at": published.isoformat() if published else None,
        "closed_at": closed.isoformat() if closed else None,
        "source_updated_at": updated.isoformat(),
        "synced_at": now.isoformat(),
        "created_at": created.isoformat(),
        "updated_at": updated.isoformat(),
    }


def _copy_batch(service: str, rows: list[dict[str, object]]) -> None:
    from django.db import connection

    if not rows:
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs'"
        )
        available = {row[0] for row in cursor.fetchall()}
    columns = [column for column in rows[0] if column in available]
    buffer = StringIO()
    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            if value is None:
                values.append("\\N")
            elif isinstance(value, list):
                values.append("{" + ",".join(value) + "}")
            else:
                text = str(value).replace("\\", "\\\\").replace("\t", " ").replace("\n", " ")
                values.append(text)
        buffer.write("\t".join(values) + "\n")
    buffer.seek(0)

    table_columns = ", ".join(columns)
    # psycopg3 exposes COPY through `cursor.copy()`, not psycopg2's copy_expert.
    with connection.cursor() as cursor, cursor.copy(
        f"COPY jobs ({table_columns}) FROM STDIN"
    ) as copy:
        copy.write(buffer.read())


def seed(service: str, count: int, batch_size: int, seed_value: int) -> None:
    directory, _ = SERVICES[service]
    os.chdir(Path(__file__).resolve().parent.parent / directory)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    sys.path.insert(0, os.getcwd())

    import django

    django.setup()

    from django.db import connection

    rng = random.Random(seed_value)
    recruiter_ids: list[str] = []
    if service == "job":
        from apps.recruiters.models import Recruiter

        for number in range(50):
            recruiter, _created = Recruiter.objects.get_or_create(
                email=f"seed-recruiter-{number}@example.com",
                defaults={"full_name": f"Seed Recruiter {number}", "company_name": "Seed Co"},
            )
            recruiter_ids.append(str(recruiter.pk))
    else:
        recruiter_ids = [str(uuid.uuid4()) for _ in range(50)]

    inserted = 0
    with connection.cursor() as cursor:
        # Bulk inserts are far faster without per-row WAL sync here; this is a
        # benchmark fixture, not production data.
        cursor.execute("SET LOCAL synchronous_commit = OFF")
    while inserted < count:
        size = min(batch_size, count - inserted)
        rows = [make_row(rng, recruiter_ids, inserted + index) for index in range(size)]
        _copy_batch(service, rows)
        inserted += size
        print(f"seeded {inserted}/{count}", flush=True)

    with connection.cursor() as cursor:
        cursor.execute("ANALYZE jobs")
        cursor.execute("SELECT count(*) FROM jobs")
        total = cursor.fetchone()[0]
    print(f"done: {total} rows in {service} database (ANALYZE complete)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed jobs for the search benchmark.")
    parser.add_argument("--service", choices=sorted(SERVICES), default="job")
    parser.add_argument("--count", type=int, default=100_000)
    parser.add_argument("--batch-size", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    seed(args.service, args.count, args.batch_size, args.seed)


if __name__ == "__main__":
    main()
