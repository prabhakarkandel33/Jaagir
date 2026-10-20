# Outage recovery

This document shows how the system behaves during a Kafka outage, during
consumer downtime, during lost events and during a poison message. The
`e2e/` suite runs all five scenarios against a real stack. Each scenario ends
with the same consistency check.

---

## 1. How to run the proof

```bash
make e2e                        # all scenarios, fresh stack, cleans up after
./tasks.ps1 e2e                 # same, on Windows

uv run --project backend python e2e/run_e2e.py --scenario A
uv run --project backend python e2e/run_e2e.py --scenario D,E
uv run --project backend python e2e/run_e2e.py --keep     # leave the stack up
```

The runner uses its own Compose project (`jobportal-e2e`) and its own host
ports (13001, 13002, 15433, 15434, 19092). It calls `down -v` first, so a run
never depends on the state of `make dev`.

The human-readable narration of scenario A is
`bash scripts/demo_kafka_outage.sh` (needs a bash shell; on Windows use the
Python runner).

---

## 2. The scenarios

| # | Failure injected | What the system must do | What the test asserts |
|---|---|---|---|
| A | Kafka container stopped | The API keeps answering. Events stay in the outbox. The replica stays valid but stale. The relay drains in order after restart. | 3 writes return 200; `outbox.pending == 3`; replica version is behind; after restart pending reaches 0 and both databases agree |
| B | Candidate consumer stopped while events flow | Events wait in Kafka. The consumer resumes from its committed offset and catches up. | The replica is unchanged while the consumer is down; it reaches the new version after restart |
| C | Replica row deleted (simulated lost event) | A full reconcile detects the missing row and repairs it. | `reconcile` returns `repaired >= 1`; the row comes back with the right version |
| D | Poison message (`schemaVersion: 99`) on the topic | The poison message goes to the DLQ. Healthy messages keep flowing. A replay applies the fixed message. | DLQ size grows; the next healthy event still applies; `dryRun` publishes nothing; the real replay restores the lost row |
| E | Topic deleted and recreated empty | No event can repair the replica, so reconciliation must rebuild it. | The row is missing after the wipe; a full reconcile restores it and the final check passes |

Every scenario ends in `assert_consistent()`:

* the set of `(id, version, status)` for all non-draft jobs is identical in
  `job_db` and `candidate_db`;
* no duplicate replica rows exist (the primary key enforces this);
* the application count is unchanged, so no reconcile pass deletes or
  rewrites applications.

---

## 3. Captured run

Real output, fresh stack, `uv run --project backend python e2e/run_e2e.py`:

```text
[e2e] project=jobportal-e2e job=http://localhost:13001 candidate=http://localhost:13002
  starting jobportal-e2e stack from docker-compose.dev-full.yml ...
[e2e] stack ready
[e2e] baseline job replicated and one application exists

[e2e] scenario A
    publish/update/close returned 2/3/4 with Kafka down
    outbox pending=3 (events are durable)
    replica stale as expected (version < 4)
[e2e] A PASS (7.5s) drained 3 events in 5.8s and converged

[e2e] scenario B
    event published, replica untouched while the consumer is stopped
[e2e] B PASS (12.6s) consumer resumed from its offset and caught up

[e2e] scenario C
    deleted the replica row (simulated lost event)
    reconcile: checked=4 repaired=1
[e2e] C PASS (12.5s) full reconcile repaired 1 row(s)

[e2e] scenario D
    removed the replica row for the job we will restore through the DLQ
    published a poison message (schemaVersion 99)
    poison message landed in jobs.events.v1.dlq
    healthy message after the poison still applied
    wrote the fixed envelope to the DLQ topic
    dry run read=2 published=0 (nothing published)
    replay read=2 published=2
[e2e] D PASS (13.4s) poison isolated in the DLQ; replay restored the lost job

[e2e] scenario E
    deleted and recreated jobs.events.v1 empty (all events are gone)
    replica is missing the job; no event can bring it back
[e2e] E PASS (15.6s) reconcile rebuilt 1 row(s) with no events available

[e2e] final consistency:
  8 non-draft jobs identical in both databases

[e2e] 5/5 scenarios passed in 110.3s
```

### Stability

The acceptance rule for M6 is three green runs in a row. Three consecutive
full runs on 2026-10-19/20:

```text
run 1: 5/5 scenarios passed in 110.3s
run 2: 5/5 scenarios passed in 110.3s
run 3: 5/5 scenarios passed in 101.8s
```

No scenario flaked. The two defects found while building the suite are
recorded in `CONTEXT.md` > Gotchas: a hanging `docker exec` Kafka helper and
an unbounded DLQ replay loop.

---

## 4. Reading the numbers

* **Scenario A, `pending=3`.** The three writes (publish, update, close) each
  inserted one outbox row in the same transaction as the state change. The
  API never waits for Kafka, so all three returned 200 while the broker was
  down. After restart the relay published them in id order and the consumer
  applied them in a single pass. `drained 3 events in 5.8s` is the time from
  `docker compose start kafka` to `pending == 0` plus replica convergence.
* **Scenario B.** The consumer's committed offset is the resume point. Events
  produced while it is down are not lost because Kafka keeps them for the
  retention window.
* **Scenario C, `checked=4 repaired=1`.** `checked` counts source rows paged
  through the snapshot API, `repaired` counts rows the reconciler had to
  upsert. One deleted replica row gives one repair.
* **Scenario D, `read=2 published=2`.** The DLQ held the poison message and
  the corrected message. The dry run read both and published none. The real
  replay published both: the poison failed again and went back to the DLQ,
  the corrected envelope applied. The replay read set is the DLQ size at the
  start of the call, so a still-invalid message cannot make the replay loop.
* **Scenario E.** After the topic wipe there is no event left to consume.
  Only `POST /internal/admin/reconcile?mode=full` can repair the replica,
  which is why reconciliation is not optional.

---

## 5. Manual check on the dev stack

```bash
./tasks.ps1 stack-up -Build
# pick a job you own and note its id
docker compose -f deploy/docker-compose.dev-full.yml --project-name jobportal-dev stop kafka
# publish / update / close the job with the recruiter token
curl.exe -H "Authorization: Bearer $TOKEN" -X POST http://localhost:3001/recruiter/jobs/$JOB_ID/close
# outbox backlog (internal token required)
curl.exe -H "X-Internal-Token: $INTERNAL_TOKEN" http://localhost:3001/internal/admin/outbox
# the replica is stale but the candidate API still answers
curl.exe http://localhost:3002/jobs/$JOB_ID
docker compose -f deploy/docker-compose.dev-full.yml --project-name jobportal-dev start kafka
# pending reaches 0 within about 30 s
curl.exe -H "X-Internal-Token: $INTERNAL_TOKEN" http://localhost:3001/internal/admin/outbox
```

---

## 6. Operations

| Symptom | Command | Expected |
|---|---|---|
| Outbox backlog grows | `GET /internal/admin/outbox` | `pending` falls after Kafka returns; `lastError` explains the wait |
| Replica drift | `POST /internal/admin/reconcile?mode=full` | `checked` and `repaired` counts; `reconcile_runs` gets a row |
| Replica state summary | `GET /internal/admin/sync-status` | last run, last repaired count, local job count, anomalies |
| Poison messages | `python e2e/...` or `scripts/replay_dlq.py --dry-run` | DLQ size, then `published` count |

`scripts/replay_dlq.py` is a thin HTTP client for
`POST /internal/admin/dlq/replay`. The replay logic lives only in
`candidate-service/apps/events/dlq.py`.
