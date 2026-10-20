#!/usr/bin/env python
"""Outage/recovery scenarios A-E (M6, ARCHITECTURE.md section 6.5).

Runs against a DEDICATED docker compose project on non-default ports, so it
never touches a running `stack-up` dev environment. This is the only place
allowed to read both databases (invariant I1 exception).

    uv run --project backend python e2e/run_e2e.py
    uv run --project backend python e2e/run_e2e.py --scenario A,C
    uv run --project backend python e2e/run_e2e.py --keep

Every scenario ends with the same assertion: the set of (id, version, status)
for all non-draft jobs is identical in the source and the replica, and the
application row count did not change.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = ROOT / "deploy" / "docker-compose.dev-full.yml"

PROJECT = "jobportal-e2e"
JOB_PORT = 13001
CAND_PORT = 13002
JOB_DB_PORT = 15433
CAND_DB_PORT = 15434
KAFKA_PORT = 19092
FRONTEND_PORT = 15174

JOB_URL = f"http://localhost:{JOB_PORT}"
CAND_URL = f"http://localhost:{CAND_PORT}"

COMPOSE_ENV = {
    "COMPOSE_PROJECT_NAME": PROJECT,
    "JOB_SERVICE_PORT": str(JOB_PORT),
    "CANDIDATE_SERVICE_PORT": str(CAND_PORT),
    "JOB_DB_PORT": str(JOB_DB_PORT),
    "CANDIDATE_DB_PORT": str(CAND_DB_PORT),
    "KAFKA_PORT": str(KAFKA_PORT),
    "KAFKA_EXTERNAL_PORT": str(KAFKA_PORT),
    "FRONTEND_PORT": str(FRONTEND_PORT),
    "FRONTEND_JOB_URL": JOB_URL,
    "FRONTEND_CANDIDATE_URL": CAND_URL,
}

BOOTSTRAP = f"localhost:{KAFKA_PORT}"
JOB_DB_URL = f"postgresql://jobportal:jobportal@localhost:{JOB_DB_PORT}/job_db"
CAND_DB_URL = f"postgresql://jobportal:jobportal@localhost:{CAND_DB_PORT}/candidate_db"


# ---------------------------------------------------------------- utilities
@dataclass
class Result:
    name: str
    ok: bool
    seconds: float
    message: str = ""


@dataclass
class Ctx:
    token: str
    recruiter_token: str = ""
    candidate_token: str = ""
    baseline_applications: int = 0
    notes: list[str] = field(default_factory=list)


def say(message: str) -> None:
    print(f"    {message}", flush=True)


def http(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 10.0,
) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


def internal(
    method: str,
    path: str,
    token: str,
    *,
    base: str = JOB_URL,
    timeout: float = 60.0,
) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"{base}{path}",
        headers={"X-Internal-Token": token, "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **COMPOSE_ENV}
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"docker compose {' '.join(args)} failed:\n{result.stderr[-3000:]}"
        )
    return result


def produce_raw(topic: str, key: str, value: dict[str, Any]) -> None:
    """Publish one message from the test host (no docker exec needed)."""
    producer = Producer(
        {
            "bootstrap.servers": BOOTSTRAP,
            "acks": "all",
            "enable.idempotence": True,
            "message.timeout.ms": 5000,
        }
    )
    producer.produce(topic, key=key.encode(), value=json.dumps(value).encode())
    pending = producer.flush(15)
    if pending:
        raise AssertionError(f"producer flush left {pending} message(s) pending")


def admin() -> AdminClient:
    return AdminClient({"bootstrap.servers": BOOTSTRAP})


def topic_names() -> set[str]:
    return set(admin().list_topics(timeout=10).topics.keys())


def topic_message_count(topic: str) -> int:
    """Total messages in a topic (sum of high - low watermarks)."""
    if topic not in topic_names():
        return 0
    consumer = Consumer(
        {
            "bootstrap.servers": BOOTSTRAP,
            "group.id": f"e2e-count-{uuid4()}",
            "enable.auto.commit": False,
        }
    )
    try:
        metadata = consumer.list_topics(topic, timeout=10)
        total = 0
        for partition in metadata.topics[topic].partitions:
            low, high = consumer.get_watermark_offsets(
                TopicPartition(topic, partition), timeout=10
            )
            total += high - low
        return total
    finally:
        consumer.close()


def delete_topic(topic: str) -> None:
    client = admin()
    futures = client.delete_topics([topic], operation_timeout=30)
    for future in futures.values():
        future.result(timeout=30)
    wait_for(
        lambda: topic not in topic_names(),
        timeout=60,
        interval=2.0,
        what="topic deletion",
    )


def create_topic(topic: str, partitions: int = 3) -> None:
    client = admin()
    futures = client.create_topics(
        [NewTopic(topic, num_partitions=partitions, replication_factor=1)],
        operation_timeout=30,
    )
    for future in futures.values():
        future.result(timeout=30)
    wait_for(
        lambda: topic in topic_names(), timeout=60, interval=2.0, what="topic creation"
    )


def wait_for(
    predicate: Any, *, timeout: float, interval: float = 1.0, what: str
) -> None:
    deadline = time.monotonic() + timeout
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return
        except Exception as exc:  # noqa: BLE001 - polling helper
            last = exc
        time.sleep(interval)
    raise AssertionError(
        f"timeout after {timeout}s while waiting for {what} (last={last!r})"
    )


def source_jobs() -> dict[str, tuple[int, str]]:
    with psycopg.connect(JOB_DB_URL, connect_timeout=5) as conn:
        rows = conn.execute(
            "SELECT id, version, status FROM jobs WHERE status <> 'DRAFT'"
        ).fetchall()
    return {str(row[0]): (row[1], row[2]) for row in rows}


def replica_jobs() -> dict[str, tuple[int, str]]:
    with psycopg.connect(CAND_DB_URL, connect_timeout=5) as conn:
        rows = conn.execute(
            "SELECT id, version, status FROM jobs WHERE status <> 'DRAFT'"
        ).fetchall()
    return {str(row[0]): (row[1], row[2]) for row in rows}


def application_count() -> int:
    with psycopg.connect(CAND_DB_URL, connect_timeout=5) as conn:
        row = conn.execute("SELECT count(*) FROM applications").fetchone()
    return int(row[0]) if row else 0


def assert_consistent(ctx: Ctx) -> dict[str, tuple[int, str]]:
    source = source_jobs()
    replica = replica_jobs()
    if source != replica:
        only_source = sorted(set(source) - set(replica))[:5]
        only_replica = sorted(set(replica) - set(source))[:5]
        drift = {
            key: (source[key], replica[key])
            for key in set(source) & set(replica)
            if source[key] != replica[key]
        }
        raise AssertionError(
            "source and replica differ: "
            f"only_source={only_source} only_replica={only_replica} drift={list(drift.items())[:5]}"
        )
    if application_count() != ctx.baseline_applications:
        raise AssertionError(
            f"applications changed: {application_count()} != {ctx.baseline_applications}"
        )
    return source


def wait_consistent(ctx: Ctx, timeout: float = 90.0) -> None:
    wait_for(
        lambda: _consistent(ctx), timeout=timeout, what="replica to match the source"
    )


def _consistent(ctx: Ctx) -> bool:
    try:
        assert_consistent(ctx)
        return True
    except AssertionError:
        return False


def outbox_pending(token: str) -> int:
    status, body = internal("GET", "/internal/admin/outbox", token)
    assert status == 200, body
    return int(body["pending"])


# ---------------------------------------------------------------- fixtures
def register_recruiter() -> str:
    email = f"recruiter-{uuid4().hex[:8]}@example.com"
    status, body = http(
        "POST",
        f"{JOB_URL}/auth/recruiters/register",
        body={
            "email": email,
            "password": "Sup3r-secret-pass",
            "full_name": "E2E Recruiter",
            "company_name": "E2E Corp",
        },
    )
    assert status == 201, body
    return body["access"]


def create_job(token: str, title: str) -> dict[str, Any]:
    status, body = http(
        "POST",
        f"{JOB_URL}/recruiter/jobs",
        token=token,
        body={
            "title": title,
            "description": f"{title} description with python and kafka",
            "company": "E2E Corp",
            "location": "Remote",
            "employment_type": "FULL_TIME",
            "skills": ["python", "kafka"],
        },
    )
    assert status == 201, body
    return body


def publish(token: str, job_id: str) -> dict[str, Any]:
    status, body = http(
        "POST", f"{JOB_URL}/recruiter/jobs/{job_id}/publish", token=token
    )
    assert status == 200, body
    return body


def update_title(token: str, job_id: str, title: str) -> dict[str, Any]:
    status, body = http(
        "PUT",
        f"{JOB_URL}/recruiter/jobs/{job_id}",
        token=token,
        body={
            "title": title,
            "description": f"{title} description with python and kafka",
            "company": "E2E Corp",
            "location": "Remote",
            "employment_type": "FULL_TIME",
            "skills": ["python", "kafka"],
        },
    )
    assert status == 200, body
    return body


def close(token: str, job_id: str) -> dict[str, Any]:
    status, body = http("POST", f"{JOB_URL}/recruiter/jobs/{job_id}/close", token=token)
    assert status == 200, body
    return body


def register_candidate() -> str:
    email = f"candidate-{uuid4().hex[:8]}@example.com"
    status, body = http(
        "POST",
        f"{CAND_URL}/auth/candidates/register",
        body={
            "email": email,
            "password": "Sup3r-secret-pass",
            "full_name": "E2E Candidate",
        },
    )
    assert status == 201, body
    return body["access"]


@contextlib.contextmanager
def reconciler_paused() -> Any:
    """Stop the scheduled reconciler so a manual pass is the only repair path."""
    compose("stop", "candidate-reconciler")
    try:
        yield
    finally:
        compose("start", "candidate-reconciler")


def wait_ready(timeout: float = 180.0) -> None:
    def _ready() -> bool:
        for url in (f"{JOB_URL}/readyz", f"{CAND_URL}/readyz"):
            status, body = http("GET", url, timeout=3)
            if status != 200 or body.get("status") != "ok":
                return False
            checks = body.get("checks", {})
            if checks.get("database") != "ok":
                return False
        return True

    wait_for(_ready, timeout=timeout, interval=2.0, what="both services to be ready")


def start_stack(build: bool) -> None:
    site = ROOT / "deploy" / "docker-compose.dev-full.yml"
    print(f"  starting {PROJECT} stack from {site.name} ...", flush=True)
    args = ["up", "-d"]
    if build:
        args.append("--build")
    compose(*args)


def stop_stack(volumes: bool) -> None:
    args = ["down", "--remove-orphans"]
    if volumes:
        args.append("-v")
    compose(*args, check=False)


# ---------------------------------------------------------------- scenarios
def scenario_a(ctx: Ctx) -> str:
    """Kafka down during publish/update/close; everything drains afterwards."""
    job = create_job(ctx.recruiter_token, "A: outage job")
    job_id = job["id"]

    compose("stop", "kafka")
    try:
        started = time.monotonic()
        published = publish(ctx.recruiter_token, job_id)
        updated = update_title(ctx.recruiter_token, job_id, "A: outage job (edited)")
        closed = close(ctx.recruiter_token, job_id)
        say(
            "publish/update/close returned "
            f"{published['version']}/{updated['version']}/{closed['version']} with Kafka down"
        )

        pending = outbox_pending(ctx.token)
        assert pending >= 3, f"expected pending outbox rows, got {pending}"
        say(f"outbox pending={pending} (events are durable)")

        replica = replica_jobs()
        stale = job_id not in replica or replica[job_id][0] < closed["version"]
        assert stale, (
            f"replica should be stale while Kafka is down, got {replica.get(job_id)}"
        )
        say(f"replica stale as expected (version < {closed['version']})")
    finally:
        compose("start", "kafka")
    wait_for(
        lambda: outbox_pending(ctx.token) == 0, timeout=120, what="outbox to drain"
    )
    drained = time.monotonic() - started
    wait_consistent(ctx)
    return f"drained {pending} events in {drained:.1f}s and converged"


def scenario_b(ctx: Ctx) -> str:
    """Consumer stopped while events flow; it catches up from the offsets."""
    compose("stop", "candidate-consumer")
    try:
        job = create_job(ctx.recruiter_token, "B: consumer down")
        job_id = job["id"]
        published = publish(ctx.recruiter_token, job_id)
        wait_for(
            lambda: outbox_pending(ctx.token) == 0, timeout=60, what="relay to publish"
        )
        replica = replica_jobs()
        assert job_id not in replica, (
            "replica must not see the event while the consumer is down"
        )
        say("event published, replica untouched while the consumer is stopped")
    finally:
        compose("start", "candidate-consumer")

    wait_for(
        lambda: replica_jobs().get(job_id, (0, ""))[0] >= published["version"],
        timeout=120,
        what="consumer to catch up",
    )
    wait_consistent(ctx)
    return "consumer resumed from its offset and caught up"


def scenario_c(ctx: Ctx) -> str:
    """Simulated lost events: bump the replica back; reconcile repairs it."""
    job = create_job(ctx.recruiter_token, "C: reconcile repair")
    job_id = job["id"]
    published = publish(ctx.recruiter_token, job_id)
    wait_for(
        lambda: replica_jobs().get(job_id, (0, ""))[0] >= published["version"],
        timeout=60,
        what="initial replication",
    )

    with psycopg.connect(CAND_DB_URL) as conn:
        conn.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        conn.commit()
    say("deleted the replica row (simulated lost event)")

    with reconciler_paused():
        status, body = internal(
            "POST", "/internal/admin/reconcile?mode=full", ctx.token, base=CAND_URL
        )
        assert status == 200, body
        assert body["repaired"] >= 1, body
        say(f"reconcile: checked={body['checked']} repaired={body['repaired']}")

        wait_consistent(ctx)
        assert job_id in replica_jobs()
    return f"full reconcile repaired {body['repaired']} row(s)"


def scenario_d(ctx: Ctx) -> str:
    """Poison message -> DLQ, healthy traffic continues, replay applies a fix."""
    good = create_job(ctx.recruiter_token, "D: healthy job")
    good_id = good["id"]
    published = publish(ctx.recruiter_token, good_id)
    wait_for(
        lambda: replica_jobs().get(good_id, (0, ""))[0] >= published["version"],
        timeout=60,
        what="healthy job to replicate",
    )

    with reconciler_paused():
        lost = create_job(ctx.recruiter_token, "D: job restored through the DLQ")
        lost_id = lost["id"]
        lost_version = publish(ctx.recruiter_token, lost_id)["version"]
        wait_for(
            lambda: replica_jobs().get(lost_id, (0, ""))[0] >= lost_version,
            timeout=60,
            what="lost job to replicate once",
        )
        with psycopg.connect(CAND_DB_URL) as conn:
            conn.execute("DELETE FROM jobs WHERE id = %s", (lost_id,))
            conn.commit()
        say("removed the replica row for the job we will restore through the DLQ")

        poison = {
            "eventId": str(uuid4()),
            "eventType": "JobPublished",
            "schemaVersion": 99,
            "aggregateId": str(uuid4()),
            "aggregateVersion": 1,
            "occurredAt": datetime.now(UTC).isoformat(),
            "payload": {"id": str(uuid4())},
        }
        produce_raw("jobs.events.v1", str(uuid4()), poison)
        say("published a poison message (schemaVersion 99)")

        wait_for(
            lambda: topic_message_count("jobs.events.v1.dlq") >= 1,
            timeout=60,
            interval=2.0,
            what="poison message in the DLQ",
        )
        say("poison message landed in jobs.events.v1.dlq")

        after = create_job(ctx.recruiter_token, "D: healthy after poison")
        after_version = publish(ctx.recruiter_token, after["id"])["version"]
        wait_for(
            lambda: replica_jobs().get(after["id"], (0, ""))[0] >= after_version,
            timeout=60,
            what="healthy traffic to continue after poison",
        )
        say("healthy message after the poison still applied")

        status, body = internal("GET", f"/internal/jobs/{lost_id}", token=ctx.token)
        assert status == 200, body
        fixed = {
            "eventId": str(uuid4()),
            "eventType": "JobPublished",
            "schemaVersion": 1,
            "aggregateId": lost_id,
            "aggregateVersion": body["version"],
            "occurredAt": datetime.now(UTC).isoformat(),
            "payload": body,
        }
        produce_raw("jobs.events.v1.dlq", lost_id, fixed)
        say("wrote the fixed envelope to the DLQ topic")

        status, dry = internal(
            "POST", "/internal/admin/dlq/replay?dryRun=true", ctx.token, base=CAND_URL
        )
        assert status == 200, dry
        assert dry["read"] >= 2, dry
        say(
            f"dry run read={dry['read']} published={dry['published']} (nothing published)"
        )

        status, replay = internal(
            "POST", "/internal/admin/dlq/replay", ctx.token, base=CAND_URL
        )
        assert status == 200, replay
        say(f"replay read={replay['read']} published={replay['published']}")

        wait_for(
            lambda: replica_jobs().get(lost_id, (0, ""))[0] >= body["version"],
            timeout=90,
            what="replayed event to apply",
        )
    wait_consistent(ctx)
    return "poison isolated in the DLQ; replay restored the lost job"


def scenario_e(ctx: Ctx) -> str:
    """Events truly gone (topic recreated empty): reconcile restores consistency."""
    job = create_job(ctx.recruiter_token, "E: events wiped")
    job_id = job["id"]
    version = publish(ctx.recruiter_token, job_id)["version"]
    wait_for(
        lambda: replica_jobs().get(job_id, (0, ""))[0] >= version,
        timeout=60,
        what="initial replication",
    )

    compose("stop", "candidate-consumer")
    try:
        delete_topic("jobs.events.v1")
        create_topic("jobs.events.v1", partitions=3)
        say("deleted and recreated jobs.events.v1 empty (all events are gone)")

        with psycopg.connect(CAND_DB_URL) as conn:
            conn.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
            conn.commit()
    finally:
        compose("start", "candidate-consumer")

    replica = replica_jobs()
    assert job_id not in replica, (
        "replica should be missing the wiped job before reconcile"
    )
    say("replica is missing the job; no event can bring it back")

    with reconciler_paused():
        status, body = internal(
            "POST", "/internal/admin/reconcile?mode=full", ctx.token, base=CAND_URL
        )
        assert status == 200, body
        assert body["repaired"] >= 1, body
        wait_consistent(ctx)
        assert job_id in replica_jobs()
    return f"reconcile rebuilt {body['repaired']} row(s) with no events available"


SCENARIOS = {
    "A": scenario_a,
    "B": scenario_b,
    "C": scenario_c,
    "D": scenario_d,
    "E": scenario_e,
}


# ---------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario", default="A,B,C,D,E", help="comma separated subset"
    )
    parser.add_argument("--keep", action="store_true", help="leave the stack running")
    parser.add_argument(
        "--no-build", action="store_true", help="reuse the cached image"
    )
    args = parser.parse_args()

    selected = [
        item.strip().upper() for item in args.scenario.split(",") if item.strip()
    ]
    unknown = [item for item in selected if item not in SCENARIOS]
    if unknown:
        parser.error(f"unknown scenario(s): {unknown}")

    token = _internal_token()
    results: list[Result] = []
    started_all = time.monotonic()

    print(f"[e2e] project={PROJECT} job={JOB_URL} candidate={CAND_URL}", flush=True)
    stop_stack(volumes=True)
    start_stack(build=not args.no_build)
    try:
        wait_ready()
        print("[e2e] stack ready", flush=True)

        ctx = Ctx(token=token)
        ctx.recruiter_token = register_recruiter()
        ctx.candidate_token = register_candidate()

        seed = create_job(ctx.recruiter_token, "E2E baseline job")
        seed_version = publish(ctx.recruiter_token, seed["id"])["version"]
        wait_for(
            lambda: replica_jobs().get(seed["id"], (0, ""))[0] >= seed_version,
            timeout=90,
            what="baseline job replication",
        )
        status, body = http(
            "POST",
            f"{CAND_URL}/jobs/{seed['id']}/applications",
            token=ctx.candidate_token,
            body={"cover_letter": "e2e baseline application"},
        )
        assert status == 201, body
        ctx.baseline_applications = application_count()
        assert ctx.baseline_applications == 1, ctx.baseline_applications
        print("[e2e] baseline job replicated and one application exists", flush=True)
        assert_consistent(ctx)

        for name in selected:
            print(f"\n[e2e] scenario {name}", flush=True)
            start = time.monotonic()
            try:
                detail = SCENARIOS[name](ctx)
                ok, message = True, detail
            except Exception as exc:  # noqa: BLE001 - report, keep going
                ok, message = False, f"{type(exc).__name__}: {exc}"
            seconds = time.monotonic() - start
            results.append(Result(name, ok, seconds, message))
            print(
                f"[e2e] {name} {'PASS' if ok else 'FAIL'} ({seconds:.1f}s) {message}",
                flush=True,
            )

        print("\n[e2e] final consistency:", flush=True)
        try:
            final = assert_consistent(ctx)
            print(
                f"  {len(final)} non-draft jobs identical in both databases", flush=True
            )
        except Exception as exc:  # noqa: BLE001 - report, do not hide the summary
            results.append(Result("final", False, 0.0, str(exc)))
            print(f"  FAIL {exc}", flush=True)
    finally:
        if not args.keep:
            stop_stack(volumes=False)

    passed = sum(1 for item in results if item.ok)
    print(
        f"\n[e2e] {passed}/{len(results)} scenarios passed in {time.monotonic() - started_all:.1f}s"
    )
    for item in results:
        if not item.ok:
            print(f"  FAILED {item.name}: {item.message}")
    return 0 if passed == len(results) else 1


def _internal_token() -> str:
    env_file = ROOT / "backend" / "services" / "job-service" / ".env"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("INTERNAL_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("INTERNAL_TOKEN not found in backend/services/job-service/.env")


if __name__ == "__main__":
    sys.exit(main())
