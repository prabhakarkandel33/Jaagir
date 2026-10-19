# CONTEXT.md

Living project memory and **the work queue**. Every session reads this first and updates it last (rules in AGENTS.md §1). Write for a stranger with zero memory.

**Sections:** 1 Status board · 2 Session plan · 3 Milestones · 4 Gotchas · 5 Decisions · 6 Blocked / needs human · 7 Session log

---

## 1. Status board

```
Current milestone : M4
State             : NOT STARTED (M3 complete)
Last session      : S5 (2026-10-19)
Next action       : M4 Candidate Service core + Kafka consumer (own DB, inbox dedup, version-guarded upsert)
Last green verify : 2026-10-19 (ruff clean, mypy x3 Success, pytest 11 + 49 + 5 = 65)
```

Progress: `[~] M0  [x] M1  [x] M2  [x] M3  [ ] M4  [ ] M5  [ ] M6  [ ] M7  [ ] M8  [ ] M9`

---

## 2. Session plan (suggested grouping; adjust freely)

| Session | Milestones | Notes |
|---|---|---|
| S1 | M0 + M1 | Proposal out the door early; scaffold + infra |
| S2 | M2 + M3 | Job Service + outbox relay |
| S3 | M4 | Candidate Service + consumer |
| S4 | M5 | Search + 100k benchmark |
| S5 | M6 | Reconciliation + outage proof (**the most important milestone; give it a fresh session**) |
| S6 | M7 | Docker + CI/CD |
| S7 | M8 | VPS deploy (human-gated) |
| S8 | M9 | Docs + requirements audit |

Rule of thumb: start a fresh session at each milestone boundary; a long session accumulates context rot and the reliability code is where subtle bugs hide.

---

## 3. Milestones

Legend: `[ ]` todo · `[x]` done with evidence · `(P1)` optional, only after all non-P1 items pass. Each milestone ends with **Acceptance**, the commands that must pass before ticking.

### M0: Proposal gate (assignment requires approval before implementation)
- [ ] Verify `docs/ASSIGNMENT.md` exists (human saves the original text there); if missing, note it in Blocked and continue.
- [ ] Read assignment vs `ARCHITECTURE.md`; record any contradiction/ambiguity in Decisions (known one: search is required in Job Service *and* the candidate-facing flow reads a replica, so search is implemented in both).
- [ ] Generate `docs/PROPOSAL.md` from ARCHITECTURE.md §1-3, §6 (summary), §7 (summary), §10, §11 (complete: CPU, RAM, storage, OS, domains, extra infra, workload assumptions, PG/Kafka placement trade-offs). Human-readable, <= 3 pages, includes the component diagram.
- [ ] Add `(HUMAN)` item to Blocked: "Send PROPOSAL.md to reviewer/DevOps; record date + response".
- **Acceptance:** `docs/PROPOSAL.md` contains explicit CPU/RAM/storage/OS/domains and the PG+Kafka placement recommendation.
- **Note:** M1-M7 need no VPS and may proceed without approval. **Do not start M8 until approval + VPS exist.**

### M1: Scaffold and local infrastructure
- [ ] Root: `uv` workspace at `backend/`, `ruff` config, `mypy` config, `pytest` config, `.gitignore`, `.editorconfig`, `opencode.json`, `Makefile` + `tasks.ps1`, `README.md`.
- [ ] `backend/packages/contracts`: pydantic event envelope + 3 event payload schemas, topic constants, `JOB_EVENT_TYPES`, unit tests (valid/invalid samples).
- [ ] Both Django service skeletons: `config/{settings,urls,asgi,wsgi}.py`, `pydantic-settings` config (fail fast), JSON logging with redaction, `GET /healthz`, `GET /readyz` (DB check; Kafka status `unknown` for now), gunicorn, DRF + `drf-spectacular` (`/docs`, `/schema`), own `DATABASE_URL` via env.
- [ ] `deploy/docker-compose.dev.yml`: `kafka` (apache/kafka KRaft, two listeners: `kafka:29092` internal, `localhost:9092` host), `job-db` (host port 5433), `candidate-db` (host port 5434), healthchecks, named volumes.
- [ ] `Makefile` with all targets from AGENTS.md §5 (unimplemented ones may print "not yet" but must exist); `tasks.ps1` mirrors it on Windows; `.env.example` per service.
- [ ] `frontend/` Vite + React + TypeScript skeleton (dev server + build).
- [ ] `.github/workflows/ci.yml`: `uv sync --all-packages` + ruff + mypy + pytest (backend job) and `npm ci && npm run build` (frontend job). Later jobs (integration with infra, Docker image build, migration check, e2e) are listed under M7.
- **Acceptance:** `make infra-up && make migrate && make verify` all green; `curl -sf localhost:3001/healthz` and `:3002/healthz` OK while `make dev` runs; each service's migrations touch only its own DB.

### M2: Job Service core
- [x] Migrations: `recruiters`, `jobs` (+ `version`, status check constraints), `outbox_events` (+ partial index). Search columns come in M5 (do not add now).
  - [2026-10-19] Done in job-service: `apps/recruiters/models.py` (custom `AUTH_USER_MODEL`, UUID PK, lower(email) unique), `apps/jobs/models.py` (status/employment check constraints, `jobs_version_positive`), `apps/outbox/models.py` (partial index `outbox_pending_idx`). Tests in `tests/test_models.py` (9 cases) assert constraints at DB level; `uv run pytest -q` -> 14 passed.
- [x] Recruiter register/login (argon2id, JWT signing, key from env as base64 PEM), `GET|PUT /recruiters/me`.
  - [2026-10-19] Done in job-service: `apps/recruiters/{serializers,services,views,urls}.py`, `apps/core/throttling.py` (`AuthRateThrottle`, scope `auth` = 10/min), `config/env.decode_pem` (base64 PEM decoded at boot), `SIMPLE_JWT` uses decoded keys + `USER_ID_CLAIM="sub"`. Routes: `POST /auth/recruiters/register`, `POST /auth/recruiters/login`, `GET|PUT /recruiters/me`. Tests `tests/test_auth.py` (11 cases). Live-verified over HTTP on :3001 (register 201, duplicate 409 `EMAIL_ALREADY_EXISTS`, login 200, `/me` 200, bad login 401 `INVALID_CREDENTIALS`). `spectacular --validate --fail-on-warn` -> exit 0.
- [x] Job commands: create (DRAFT), update, publish, close with the state machine (`DRAFT->PUBLISHED->CLOSED`; illegal transitions -> 409 `INVALID_STATE_TRANSITION`), ownership enforced (other recruiter's job -> 404), `version = version + 1` on every write.
  - [2026-10-19] Done in job-service: `apps/jobs/{serializers,services,views,urls}.py`, `apps/core/permissions.py` (`IsRecruiter` checks the token `role` claim), `apps/core/db.py` (`with_tx`). Commands lock the row (`select_for_update`) then bump `version`. Tests in `tests/test_jobs.py` (13 cases).
- [x] `withTx(fn)` helper; publish/update-while-published/close insert an outbox row **in the same tx** (envelope from `packages/contracts`, payload = full snapshot).
  - [2026-10-19] `apps/outbox/services.py` `enqueue_job_event` builds `EventEnvelope`/`JobSnapshot` from `contracts`; the outbox row stores the full envelope JSON. Rollback test proves no outbox row and no version change when the emitter raises.
- [x] Recruiter list with pagination; public `GET /jobs/:id` returns PUBLISHED only.
  - [2026-10-19] `GET /recruiter/jobs` uses `apps.core.pagination` (`{items,page,pageSize,total}`), scoped to the owner. `GET /jobs/:id` returns 404 for DRAFT and CLOSED.
- [x] Uniform error format; rate-limit on auth routes; OpenAPI schemas for all routes.
  - [2026-10-19] All routes documented with `@extend_schema`; `spectacular --validate --fail-on-warn` exit 0. Auth routes throttled at 10/min.
- **Acceptance:** integration tests cover: state machine, ownership, outbox row exists with correct `aggregate_version`, **tx rollback leaves no outbox row and no job change**, draft edits emit nothing. `make verify` green.

### M3: Outbox relay and producer — M3 COMPLETE
- [x] Kafka client module: lazy/background connect with retry; **service boots and serves HTTP with Kafka down (I9)**. `ensureTopics` (`jobs.events.v1` x3 partitions, DLQ x1) runs in the background until it succeeds.
  - [2026-10-19] Done in job-service: `apps/core/kafka.py` (`KafkaClient` with `status: unknown|up|degraded`, `ensure_ready()`, `start_monitor()/stop_monitor()`, `publish()`, `KafkaUnavailableError`, `TOPIC_SPECS`, `get_kafka_client()` lru_cache). Topics verified live: `kafka-topics.sh --describe` -> `jobs.events.v1` PartitionCount 3, `.dlq` PartitionCount 1, both RF 1.
- [x] Idempotent producer, `acks=-1`, key=aggregateId, headers per ARCHITECTURE §5.
  - [2026-10-19] Producer config `enable.idempotence=True`, `acks=all`, `message.timeout.ms` from env; `publish()` sets key=aggregateId and headers `event-type`/`event-id`/`schema-version` (constants in `packages/contracts`).
- [x] Relay loop per §6.1 (advisory lock, `FOR UPDATE SKIP LOCKED`, ordered, backoff capped at 30 s, stops batch on first failure, `OUTBOX_RELAY_ENABLED` flag, graceful stop).
  - [2026-10-19] `apps/outbox/relay.py` (`relay_once`/`_drain`, `select_for_update(skip_locked=True)` in id order, `pg_try_advisory_lock(4242001)`, `backoff_seconds` cap 30 s, stops batch on first failure) + `apps/outbox/management/commands/run_relay.py` (monitor-driven; publishes only while `status == "up"`; SIGINT/SIGTERM graceful stop; respects `OUTBOX_RELAY_ENABLED`).
- [x] `GET /internal/admin/outbox` (+ `X-Internal-Token` guard); `/readyz` reports `kafka: up|degraded` without failing readiness.
  - [2026-10-19] `apps/core/internal.py` (`require_internal`, `hmac.compare_digest`), `apps/outbox/views.py` + `urls.py` (`{pending, oldestPendingAgeSeconds, lastError, publishedLastHour}`), `apps/core/views.py` `readyz` reports kafka status and lazily starts the monitor.
- [x] Tests: (a) happy path: published event arrives on topic with valid envelope; (b) producer failing -> rows pending, API still 2xx, `attempts` grows; (c) recovery -> backlog drained **in order**; (d) crash-between-ack-and-mark simulation -> duplicate delivery is possible and acceptable (assert same `eventId`).
  - [2026-10-19] `tests/test_relay.py` (6 cases, `FakePublisher` with `fail_times`; covers drain-in-order, backoff/growth, stop-batch-on-failure) and `tests/test_internal.py` (5 cases).
- **Acceptance:** `make verify` green. Manual: `docker compose -f deploy/docker-compose.dev.yml stop kafka` -> create + publish a job via API -> 200, `/internal/admin/outbox` shows `pending >= 1` -> `start kafka` -> pending 0 within 30 s.
  - [2026-10-19] `./tasks.ps1 verify` -> ruff clean, format 88 files, mypy Success x3, pytest 11 + 49 + 5 = 65. Live outage: stop kafka -> publish HTTP 200 -> outbox `pending:1, lastError:"1 message(s) not delivered before timeout"` -> start kafka -> pending 1 -> 1 -> 0 within ~10 s; final `{pending:0, publishedLastHour:5}`.

### M4: Candidate Service core and consumer
- [ ] Migrations: `candidates`, `jobs` (replica), `applications` (with `UNIQUE (candidate_id, job_id)`), `processed_events`.
- [ ] Candidate register/login/profile (candidate-issued JWT; also loads Job Service **public key** from env for recruiter tokens).
- [ ] Consumer per §6.2: one DB tx (inbox insert + version-guarded upsert), 3 retries with backoff for transient errors, non-retryable -> DLQ immediately, DLQ headers, offset committed after DLQ publish. One shared `upsertJobFromSnapshot()` function (reused by M6).
- [ ] Boot independent of Kafka (I9); `/readyz` shows consumer state.
- [ ] Apply: job must exist locally and be `PUBLISHED` (else 404 `JOB_NOT_FOUND` / 409 `JOB_NOT_OPEN`); duplicate -> 409 `APPLICATION_ALREADY_EXISTS` via SQLSTATE 23505 (no check-then-insert race); store title/company snapshot.
- [ ] `GET /candidates/me/applications` (paginated, newest first, includes status) + detail.
- [ ] `GET /recruiter/jobs/:jobId/applications` (recruiter JWT from Job Service; ownership via replica `recruiter_id`; paginated). `(P1)` `PATCH /recruiter/applications/:id/status`. `(P1)` sync fallback `GET /internal/jobs/:id` when a job is missing locally (timeout 2 s; never blocks when Job Service is down).
- **Acceptance (tests):** same event delivered twice -> one row, one `processed_events`; v3 then v2 -> stays v3; JobClosed -> apply gives 409 `JOB_NOT_OPEN`; **10 concurrent applies by one candidate -> exactly one 201, nine 409, one row**; malformed message -> lands in DLQ and next message still processes; recruiter B cannot read recruiter A's applications. `make verify` green.

### M5: Search (PostgreSQL FTS)
- [ ] Migrations in **both** services (per ARCHITECTURE §7): trigger function + `search_vector`, backfill existing rows, partial GIN on `search_vector`, GIN on `skills`, btree indexes. Down migrations drop them.
- [ ] Query module with `websearch_to_tsquery`, weighted `ts_rank_cd`, tie-breakers, filters (employmentType, location, skills), `page/pageSize`, `total`. Empty query = browse. Endpoints: Job Service `GET /jobs`, Candidate Service `GET /jobs`. Unpublished and closed never returned.
- [ ] `scripts/seed-jobs.ts` (`make seed N=100000`): realistic varied vocabulary from word lists (no heavy deps), ~90% PUBLISHED / 5% CLOSED / 5% DRAFT, inserted in batches. Candidate side is seeded through its own DB path (it is a replica; for benchmark seeding direct insert is allowed inside `scripts/` only).
- [ ] `scripts/explain-analyze.sh` / `make explain`: runs >= 3 representative queries with `EXPLAIN (ANALYZE, BUFFERS)`, once with indexes disabled/dropped (Seq Scan baseline) and once with them (Bitmap Index Scan on GIN).
- [ ] `docs/search-performance.md`: indexing strategy explained, query shapes, real captured plans and timings, caveats.
- **Acceptance (tests):** unpublished/closed excluded; title-match outranks description-match; pagination is stable and non-overlapping; weird input (`"`, `'`, `&`, `:*`, empty, 10k chars) never causes 500 and cannot inject SQL. `make explain` output shows GIN usage at 100k rows.

### M6: Reconciliation, DLQ replay and outage proof (MOST IMPORTANT)
- [ ] Job Service `GET /internal/jobs/snapshot?after&limit` per §6.3 (non-DRAFT, keyset by id, full payloads, token-guarded).
- [ ] Candidate reconciler: full + incremental modes, schedule (30 s after boot, 5 min incremental, nightly full), uses shared `upsertJobFromSnapshot()`, writes `reconcile_runs`, logs anomalies, on-demand `POST /internal/admin/reconcile?mode=`, `GET /internal/admin/sync-status`.
- [ ] `scripts/replay-dlq.ts` (`--dry-run`, `--limit`) and `POST /internal/admin/dlq/replay`.
- [ ] `e2e/` scenarios (automated, `make e2e`) and `scripts/demo-kafka-outage.sh` (same story, human-readable PASS/FAIL narration):
  - **A** Kafka stopped -> publish, update, close jobs -> API OK, outbox pending > 0, candidate replica stale -> Kafka started -> outbox drains, replica matches.
  - **B** Candidate consumer stopped while events flow -> restarted -> catches up from offsets.
  - **C** Simulated lost events (delete replica rows / lower versions directly in `candidate_db`) -> `reconcile` repairs, `repaired` count matches.
  - **D** Poison message on topic -> goes to DLQ, healthy messages keep flowing -> fix cause -> `replay-dlq` -> applied.
  - **E** Topic deleted/recreated (or consumer offsets reset to end) so events are truly gone -> reconcile restores full consistency.
  - Final assertion in every scenario: `(id, version, status)` of all non-draft jobs identical between Job Service snapshot and Candidate replica; no duplicate rows; applications untouched.
- [ ] `docs/outage-recovery.md`: scenario descriptions + **captured real output** of the demo script.
- **Acceptance:** `make e2e` all scenarios pass **three runs in a row** (flakiness check); `docs/outage-recovery.md` contains real transcripts. Record any flake root cause in Gotchas.

### M7: Containerization and CI/CD
- [ ] Dockerfiles for both services (multi-stage, build context = repo root because of `packages/contracts`, `node:22-slim`, non-root, prod deps only, `HEALTHCHECK` via node fetch, `.dockerignore`).
- [ ] `deploy/docker-compose.prod.yml`: caddy, kafka (heap capped, volume), job-db, candidate-db (volumes, healthchecks), job-service, candidate-service, `*-migrate` one-shot services, log rotation, `mem_limit`s per §11 budget, only Caddy publishes ports, private network.
- [ ] `deploy/Caddyfile`: both domains from env, `/internal/*` -> 404, security headers, `reverse_proxy`; support `tls internal` / staging ACME for testing.
- [ ] `deploy/scripts/`: `bootstrap-vps.sh` (docker, ufw, deploy user, dirs), `render-env.sh` (secrets -> `.env`, chmod 600, never echoed), `deploy.sh`, `rollback.sh`, `backup-db.sh` (+ cron example).
- [ ] `ci.yml` complete (lint, typecheck, tests with compose infra, **migration check** up/down/up per service on fresh DB + immutability check, image build, e2e on main). `deploy.yml` (GHCR push, SSH deploy, health gate, auto-rollback).
  - CI job list to reach (M1 has only the first + frontend): (1) ruff lint + format check, (2) mypy per service, (3) unit tests, (4) **integration tests** with `docker compose ... up -d --wait` infra, (5) **migration check** (fresh DB migrate, reverse, forward; fail if a committed migration changed), (6) **Docker image build** for both services + frontend (no push on PR), (7) `actionlint` on the workflow YAML, (8) e2e outage suite on `main`, (9) secret scan (`gitleaks` or `git grep -nEi 'password|secret|BEGIN .*KEY'`), (10) `uv.lock` / `package-lock.json` freshness check. (P1) advisory CVE scan (`pip-audit`, `npm audit`).
- [ ] `docs/deployment.md` listing required GitHub secrets/variables and VPS prerequisites.
- **Acceptance:** `docker build` both images OK; `make prod-local` brings the whole stack up behind Caddy and both `/readyz` respond via Caddy; `/internal/*` through Caddy -> 404; `deploy.sh` rollback proven locally by deploying a deliberately broken tag; workflow YAML passes `actionlint` (if available). Real GitHub run is verified by the human.

### M8: VPS deployment (HUMAN-GATED)
- [ ] Preconditions (see Blocked): proposal approved, VPS up, DNS A records resolving, SSH key + GitHub secrets set.
- [ ] Run `bootstrap-vps.sh`; first deploy through the workflow; fix environment-specific issues (record every one in Gotchas; this milestone generates the most of them).
- [ ] `scripts/smoke.sh https://jobs.<domain> https://candidates.<domain>`: recruiter register/login -> create+publish job -> appears in candidate search within seconds -> candidate registers -> applies -> duplicate apply 409 -> history shows it -> recruiter sees the application.
- [ ] Run the outage demo on the VPS (stop/start Kafka container) and append the transcript to `docs/outage-recovery.md`.
- [ ] Test a deliberate bad deploy -> auto-rollback; record in `docs/runbook.md`.
- [ ] Record the live URLs in README.
- **Acceptance:** both URLs live over valid HTTPS; smoke passes; outage + rollback evidence captured.

### M9: Documentation and final audit
- [ ] `README.md`: overview, architecture diagram, local setup (5 commands max), running tests/e2e, deployment, recovery procedures, troubleshooting (seeded from Gotchas), live URLs, API doc links.
- [ ] `docs/API.md` generated/updated from OpenAPI (`make openapi`) with example requests.
- [ ] `docs/runbook.md` finalized (rollback, backup/restore, Kafka loss, DLQ replay, stuck relay, cert problems).
- [ ] Walk the traceability table in ARCHITECTURE.md §14 and fill "Evidence" for every row; fix any gap found.
- [ ] Clean-clone test in a temp dir: follow README exactly; it must work.
- [ ] Final sweep: no secrets committed (`git grep -nEi 'password|secret|BEGIN .*KEY'`), no stray TODOs, `.env.example` complete.
- **Acceptance:** traceability table fully evidenced; clean-clone test passes; `make verify` and `make e2e` green.

---

## 4. Gotchas and discoveries (append-only; newest last; mark wrong entries as struck through, do not delete)

Format: `- [YYYY-MM-DD, Mx] Symptom/surprise -> cause -> fix/rule.`

**Pre-seeded from design analysis (unverified; confirm or strike when you meet them):**

- [seed, M5] `GENERATED ALWAYS AS (... array_to_string(skills,' ') ...)` fails ("generation expression is not immutable") -> `array_to_string` is STABLE -> use a trigger to maintain `search_vector`.
- [seed, M5] Partial GIN index is ignored unless the query contains the literal predicate `status = 'PUBLISHED'` (a bind parameter will not match). Keep the literal.
- [seed, M5] On small tables the planner picks Seq Scan even with the index -> benchmark at 100k rows, run `ANALYZE jobs;` after seeding; for demos you may `SET enable_seqscan = off` but say so in the doc.
- [seed, M5] `websearch_to_tsquery` never raises on odd user input (unlike `to_tsquery`), prefer it. It does not do prefix matching.
- [seed, M3] kafkajs idempotent producer: `idempotent: true`, `maxInFlightRequests: 1`, `acks: -1`. Set `KAFKAJS_NO_PARTITIONER_WARNING=1` to silence the noise.
- [seed, M1] Single-broker Kafka needs `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1`, `KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1`, `KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1`, and topic replication factor 1, otherwise the idempotent producer / consumer group hang.
- [seed, M1] Kafka advertised listeners: host processes (`make dev`) need `localhost:9092`; containers need `kafka:29092`. Use two listeners; wrong advertised address = connect succeeds then metadata calls time out.
- [seed, M3/M4] Services must create topics themselves (`ensureTopics`) or the consumer subscribes to a non-existent topic on first boot. Retry in the background.
- [seed, M4] In kafkajs, if `eachMessage` throws, the consumer retries/restarts and can block the partition -> catch everything, route to DLQ, never rethrow for poison messages.
- [seed, M3] Relay ordering: `SKIP LOCKED` with multiple relays can reorder; one active relay via `pg_try_advisory_lock`, and the version guard makes reordering harmless anyway.
- [seed, M2] Outbox insert must use the **same** `PoolClient` as the state change; accidentally using the pool = separate tx = the exact bug the outbox exists to prevent. Test rollback explicitly.
- [seed, M1] node-pg-migrate SQL files need the `-- Up Migration` / `-- Down Migration` markers; never edit a committed migration (I5).
- [seed, M2] PEM keys in env lose newlines. Store base64 of the PEM and decode at boot.
- [seed, M2] Prefer `lower(email)` unique index over `citext` (no extension privileges needed for the app role).
- [seed, M7] `node:22-slim` has no `curl`; compose/Docker healthchecks must use `node -e "fetch('http://localhost:3001/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"`.
- [seed, M7] Docker build context must be the repo root (workspaces + `packages/contracts`), and `.dockerignore` must exclude `node_modules`, `.git`, `dist`.
- [seed, M7/M8] Caddy needs DNS pointing at the VPS and ports 80/443 open before it can issue certs; use ACME staging or `tls internal` while testing to avoid Let's Encrypt rate limits.
- [seed, M6] e2e tests use separate docker compose project name / ports to avoid colliding with `make dev` infra. Wait for health (poll), never `sleep` fixed durations.
- [seed, M8] GitHub Actions SSH deploy: use a dedicated key, `StrictHostKeyChecking` handled via pinned `known_hosts`, and pass secrets via stdin to `render-env.sh`, never as command-line args (they show up in `ps` and logs).

*(Append real discoveries below this line.)*

- [2026-10-18, M1] Windows dev box has NO system Python and NO `make`. `uv 0.11.23` is present and manages CPython 3.12.13 (`uv python install 3.12`). Fix: run everything through `uv run`; use `tasks.ps1` locally, keep `Makefile` for CI/Linux. Do not require system Python.
- [2026-10-18, M1] The whole stack changed from Node to Django (see Decisions). Cause: human direction. Rule: milestone text M2-M9 and pre-seeded Gotchas still mention Node tooling (`kafkajs`, `node-pg-migrate`, `node:22-slim`, zod, pino). Treat those names as stale; reword each milestone as it is attempted, and record the rewording here.
- [2026-10-18, M1] `docs/ASSIGNMENT.md` is still missing (no `docs/` dir). M0 proposal is blocked on the human; M1+ proceed without it.
- [2026-10-18, M1] `uv sync` (plain) does NOT install workspace members that are non-packages, so `contracts` and pydantic get uninstalled. Fix: always `uv sync --all-packages` (Makefile `sync`, `tasks.ps1 sync`, and CI).
- [2026-10-18, M1] pydantic v2: `PostgresDsn` has no `.parsed` attribute (that is pydantic v1). Fix: `urlparse(str(dsn))` in `config/db.py`.
- [2026-10-18, M1] mypy fails with `Duplicate module named "apps"` when both services are checked in one run (both expose top-level `apps`/`config`). Fix: run mypy once per service (`make typecheck` / `tasks.ps1 typecheck`).
- [2026-10-18, M1] Django 6.1 was pulled in transitively by `django-stubs`. Fix: pin `django>=5.2,<6` and `django-stubs>=5.1,<6` in `backend/pyproject.toml` dev group.
- [2026-10-18, M1] drf-spectacular serves `/schema` as `application/vnd.oai.openapi`, not JSON. In tests assert on `response.content`, not `response.json()`.
- [2026-10-18, M1] Windows dev box has no `make`; `tasks.ps1` is the local equivalent and mirrors every target. CI uses `Makefile` on Ubuntu.
- [2026-10-18, M1] `GET /docs` returned 500 `TemplateDoesNotExist: drf_spectacular/swagger_ui.html`. Cause: `TEMPLATES = []`. Fix: enable `DjangoTemplates` with `APP_DIRS: True` in both `config/settings/base.py`; regression test added (`test_swagger_ui_is_served`).
- [2026-10-18, M1] In PowerShell `curl` is an alias for `Invoke-WebRequest` (prompts, parses HTML). Use `curl.exe` for raw checks.
- [2026-10-19, M2] Switching `AUTH_USER_MODEL` after `auth` migrations were applied breaks `migrate` history. Fix: wipe the dev volumes once (`docker compose -f deploy/docker-compose.dev.yml down -v` then `up -d --wait`) and re-run `migrate`; no data existed. Do this before M2 auth work on any old dev DB.
- [2026-10-19, M2] Django requires `USERNAME_FIELD` to carry `unique=True` (`auth.E003`), so `email` has both a field-level unique constraint and a functional `Lower("email")` constraint. Writes go through `RecruiterManager`, which lowercases the address.
- [2026-10-19, M2] mypy without the django-stubs plugin reports `var-annotated` on every model field. Fix: per-service `mypy.ini` enables `mypy_django_plugin.main` with `django_settings_module = config.settings.test`, and `tasks.ps1`/`Makefile` run mypy from each service directory. Contracts still check from `backend/` without the plugin.
- [2026-10-19, M2] `config/settings/test.py` uses the MD5 hasher for speed, so the argon2 assertion uses `@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"])`.
- [2026-10-19, M2] Generated migrations are excluded from ruff (`extend-exclude = ["**/migrations"]`); `models.py` ignores `RUF012`/`DJ001` because Django `Meta` options and nullable `last_error` are intentional.
- [2026-10-19, M2] `ApiError` (config/exceptions.py) MUST set `self.status_code` in `__init__`. DRF reads `status_code` from the instance/class, not from `code`; passing the HTTP status as DRF's `code=` string arg left every domain error at HTTP 500 (envelope was right, status was wrong). Fixed by setting `self.status_code = http_status`.
- [2026-10-19, M2] SimpleJWT's `USER_ID_CLAIM` defaults to `user_id`, not `sub`. ARCHITECTURE.md section 9 requires `sub`, so `SIMPLE_JWT["USER_ID_CLAIM"] = "sub"` is set in `config/settings/base.py`.
- [2026-10-19, M2] ES256/RS256 signing needs PyJWT's crypto backend: added `cryptography>=43` to `job-service` deps (was absent; tokens would raise at sign time).
- [2026-10-19, M2] Test JWT keys: `config/settings/test.py` generates an ephemeral ES256 keypair at import and overrides `SIMPLE_JWT`, so tests never need provisioned `.env` keys. Dev keys live in the git-ignored `.env` as base64 PEM.
- [2026-10-19, M2] PowerShell mangles inline JSON for `curl.exe` (`"` escaping). Use `--data-binary "@file.json"` with a temp file for HTTP checks instead of `-d "{...}"`.
- [2026-10-19, M2] `uv run python manage.py runserver ... --noreload` leaves TWO processes (the `uv` parent and the `python` child). `Stop-Process` on the parent leaves the child holding port 3001, so a later server silently fails to bind and old requests hit the STALE URLconf (new routes 404). Fix: kill the actual listener pid(s) (`Get-NetTCPConnection -LocalPort 3001 -State Listen`) in a loop until none remain. Symptom to watch for: `/jobs` 404 with the Django debug page listing only the old routes.
- [2026-10-19, M2] `IsRecruiter` must check `request.auth` (the JWT payload), not `request.user` alone; `force_authenticate` sets only `request.user`, so recruiter-route tests must send a real `Authorization: Bearer` token (helper `auth_client` uses `issue_access_token`).
- [2026-10-19, M3] `confluent_kafka.AdminClient` created as a local variable is garbage-collected before its `create_topics` futures resolve. Result: `_DESTROY: handle is terminating`, topics never created, and every produce then fails with `UNKNOWN_TOPIC_OR_PART` / `_MSG_TIMED_OUT`. Fix: hold ONE persistent `AdminClient` on the `KafkaClient` instance (`self._admin_client`, lazy) and reuse it in `_ensure_topics()`/`_ping()`.
- [2026-10-19, M3] If the relay publishes while the broker is not ready, each row burns the full 5 s `message.timeout.ms` before failing (slow, noisy). Fix: `run_relay` starts the monitor and only calls `relay_once` when `client.status == "up"`; rows stay pending with no timeout burn while Kafka is down.
- [2026-10-19, M3] The relay's own process can be started twice by accident (each `uv run` leaves a parent + child). The `pg_try_advisory_lock` makes the spare relay a no-op, but avoid duplicates when scripting: kill `run_relay`/`runserver` python pids before starting.

---

## 5. Decisions log (append-only)

Format: `- [YYYY-MM-DD, Mx] Decision. Why. Alternatives rejected.`

- [2026-10-19, M3] The relay publishes only while `KafkaClient.status == "up"` (monitor-driven) instead of attempting on every cycle. Why: a broker outage then leaves rows pending with no per-row flush timeout and no escalating backoff, so recovery is a clean drain. Rejected: keep attempting and rely on backoff (5 s stall per row, noisier logs).
- [2026-10-19, M2] The recruiter IS the Django auth user (`AUTH_USER_MODEL = recruiters.Recruiter`, `AbstractBaseUser`). Why: SimpleJWT, argon2id hashing, and `last_login` work without a second profile table. Rejected: `auth.User` + `Recruiter` profile (two tables, needless join).
- [2026-10-19, M2] UUID primary keys use Python-side `uuid.uuid4`, not `gen_random_uuid()`. Why: no DB default needed, works in bulk tests without a round trip. Rejected: `db_default` (harder to introspect, migration noise).
- [2026-10-19, M2] Auth endpoints return a single access token (no refresh endpoint). Why: assignment only needs login -> access token; `role`/`iss`/`sub` claims are the contract (ARCHITECTURE.md section 9). Rejected: exposing SimpleJWT refresh flow (extra surface, not required).
- [2026-10-19, M2] The outbox `payload` column stores the **full envelope JSON** (not just the snapshot). Why: the M3 relay can send the value bytes unchanged and the headers come from the same object; the `event_type`/`aggregate_id`/`aggregate_version` columns stay for querying. Rejected: storing only the snapshot (relay would rebuild the envelope and could drift).


- [design] Stack = Node 22/TypeScript/Fastify/raw SQL. Why: fast agent iteration, ~half the RAM of a JVM stack, full SQL control for FTS/outbox. Rejected: Spring Boot (RAM, slower iteration), ORMs (hide FTS/outbox semantics).
- [design] Search implemented in both services (Job Service `GET /jobs`, Candidate Service `GET /jobs` over replica). Why: the assignment says the Job Service exposes search *and* that the candidate replica exists so candidates can search/apply; also keeps candidate search alive during Job Service downtime.
- [design] Event payload = full snapshot + monotonically increasing `version`. Why: makes consumer idempotent/order-safe and lets reconciliation share the same upsert.
- [design] No unpublish; CLOSED is terminal. Why: simplifies replica semantics; assignment only requires create/publish/update/close.
- [design] Recruiter applications are served by the Candidate Service using the Job Service's JWT public key. Why: applications live there; avoids a sync dependency on Job Service.
- [design] Two Postgres containers (one per service) rather than one instance with two DBs. Why: strongest defensible ownership story for ~0.3 GB extra RAM.

**Stack change (human-directed, supersedes the `[design]` stack line above):**

- [2026-10-18, M1] Stack = **Python 3.12 + Django 5 + DRF**, `uv` workspaces, Dockerized dev/prod, **Vite + React + TypeScript** frontend, Docker Compose + GitHub Actions. Why: human instruction at project start; the earlier "Node 22/TS/Fastify" line was the pre-approved draft and is now stale. Rejected: keeping Node (contradicted by the human's direction).
- [2026-10-18, M1] Rejected: the "no frontend" non-goal in ARCHITECTURE.md §13. Why: the human approved a React frontend. ARCHITECTURE.md §13 updated in the same commit (AGENTS.md §9).
- [2026-10-18, M1] Postgres remains via `django.contrib.postgres` with `SearchVector`/`SearchQuery` + `GinIndex`; FTS and the outbox stay SQL-level. Why: invariant I4 must hold.
- [2026-10-18, M1] Kafka client = `confluent-kafka` (librdkafka), idempotent producer, `acks=all`. Why: native idempotent producer and stable librdkafka; `kafka-python` lacks it. Rejected: `kafkajs` (Node, gone with the stack), `kafka-python` (unmaintained, no idempotence).
- [2026-10-18, M1] Background workers (relay, consumer, reconciler) are Django management commands started as separate containers. Why: no extra broker; keeps the "background loop" design in ARCHITECTURE.md §6. Rejected: Celery (needs Redis/RabbitMQ).
- [2026-10-18, M1] Migrations = Django migrations (Python), replacing `node-pg-migrate` SQL files. Why: ORM-native; I5 immutability still enforced. Rejected: raw SQL migration tooling (extra dependency, diverges from the ORM).
- [2026-10-18, M1] Auth = argon2id (Django default hasher) + `djangorestframework-simplejwt` (ES256/RS256). Why: ORM-free, matches ARCHITECTURE.md §9. Rejected: `jose` (Node, gone).
- [2026-10-18, M1] Tests target real behavior only. No coverage padding, no assertions written for their own sake. Why: human instruction. Consequence: M1 ships few tests (contract validation, `/healthz`, `/readyz`, uniform 404); the reliability paths (outbox, consumer, reconciler, DLQ) get mandatory, meaningful tests in M3/M4/M6.
- [2026-10-18, M1] Local `.env` files exist on the dev machine and are git-ignored; `.env.example` keeps placeholders only (I6). Why: services need real dev values to boot; secrets must never be committed.
- [2026-10-18, M1] Services are non-package `uv` workspace members (run in place), not installed distributions. Why: both projects expose top-level `config/` and `apps/`; installing both into one shared venv collides. Rejected: installing each service (name clash), namespacing every app (unidiomatic Django).

---

## 6. Blocked / needs human

- [ ] (HUMAN) Save the original assignment text as `docs/ASSIGNMENT.md`.
- [ ] (HUMAN, M0) Send `docs/PROPOSAL.md` to reviewer/DevOps. Sent: ____ Response: ____
- [ ] (HUMAN, M8) VPS provisioned (IP: ____), domains: `jobs.____` / `candidates.____`, A records resolving.
- [ ] (HUMAN, M8) GitHub environment secrets set (see `docs/deployment.md` once M7 is done): SSH key/host/user, DB passwords, JWT keys (base64 PEM), `INTERNAL_TOKEN`.

---

## 7. Session log (append-only; newest last)

Template:

```
### Session N: YYYY-MM-DD: Mx[-My]
- Did:
- Verified (commands + result):
- Not done / left half-way (exact file + state):
- Gotchas/decisions added: (refs)
- Next session should start with:
```

*(Entries below.)*

### Session 1: 2026-10-18: M0 (partial) + M1 (in progress)
- Did: replaced the Node stack with Django/DRF/uv/Docker/React (human-directed) and updated AGENTS.md §2/§3/§5/§6/§8 + §10 (Skills), ARCHITECTURE.md stack lines, CONTEXT decisions. Built the `backend/` uv workspace (`contracts`, `job-service`, `candidate-service`), the dev compose (Kafka KRaft + 2 Postgres), `Makefile` + `tasks.ps1`, the Vite/React/TS frontend, the CI skeleton, and local `.env` files.
- Verified (commands + result):
  - `./tasks.ps1 verify` -> ruff "All checks passed", format "54 files already formatted", mypy "Success" x3 (contracts/job/candidate), pytest 11 + 5 + 5 passed.
  - Live: `/healthz`, `/readyz`, `/schema`, `/docs` all 200 on :3001 and :3002 (`curl.exe`).
  - `docker compose -f deploy/docker-compose.dev.yml ps` -> kafka, job-db, candidate-db all `(healthy)`.
  - `uv run python manage.py migrate` in each service -> auth/contenttypes applied to its own DB only.
  - `npm run build` in `frontend/` -> built in ~2s.
- Not done / left half-way: `docs/PROPOSAL.md` (M0), Dockerfiles (M7), integration + Docker-build + e2e CI jobs (M7), JWT keypairs (M2), `make` is not installed on this Windows box (use `tasks.ps1`).
- Gotchas/decisions added: stack-change decisions; "tests are real-behavior only"; non-package workspace members; `uv sync --all-packages`; pydantic `PostgresDsn.parsed`; mypy duplicate `apps`; Django 6 pin; drf-spectacular content-type.
- Next session should start with: confirm `make`/`tasks.ps1 dev` serves `/healthz` on 3001 and 3002, tick M1, then write `docs/PROPOSAL.md` (M0) before starting M2.

### Session 2: 2026-10-19: M2 (data layer)
- Did: fixed the `/docs` 500 (`TEMPLATES` was empty) and added a regression test; added `apps/recruiters/models.py` (custom `AUTH_USER_MODEL`), `apps/jobs/models.py`, `apps/outbox/models.py` with their initial migrations; enabled the django-stubs mypy plugin per service; excluded generated migrations from ruff; added `tests/test_models.py`.
- Verified (commands + result):
  - `./tasks.ps1 verify` -> ruff "All checks passed", format "64 files already formatted", mypy "Success" x3, pytest 11 + 14 + 5 passed.
  - `uv run python manage.py migrate` on a fresh `job_db` -> recruiters, jobs, outbox migrations applied.
  - `curl.exe` after the settings fix -> `/docs` 200 on :3001 and :3002.
- Not done / left half-way: M2 auth (`register`, `login`, `GET|PUT /recruiters/me`), job command endpoints, `withTx`, outbox inserts on publish/update/close, recruiter list, public `GET /jobs/:id`, throttling/OpenAPI for these routes. `docs/PROPOSAL.md` (M0) still blocked on `docs/ASSIGNMENT.md`.
- Gotchas/decisions added: `TEMPLATES` empty breaks Swagger UI; `curl` alias; AUTH_USER_MODEL switch needs fresh dev DB; USERNAME_FIELD must be `unique=True`; django-stubs plugin per-service; MD5 test hasher vs argon2 assertion; ruff excludes migrations; recruiter = auth user; Python-side UUIDs.
- Next session should start with: M2 auth endpoints in `apps/recruiters` (serializers, views, urls, SimpleJWT signing from base64 PEM env), tests for register/login/me, then job commands + outbox in the same tx.

### Session 3: 2026-10-19: M2 (auth slice)
- Did: implemented the M2 auth slice in job-service: `apps/recruiters/{serializers,services,views,urls}.py` (`RegisterSerializer`, `LoginSerializer`, `RecruiterSerializer`, `RecruiterUpdateSerializer`), `apps/core/throttling.py` (`AuthRateThrottle` scope `auth` = 10/min), `config/env.decode_pem` + `jwt_*_pem` properties (base64 PEM decoded at boot), `SIMPLE_JWT` wired to the decoded keys with `USER_ID_CLAIM="sub"`, `cryptography>=43` added to deps, routes included from `config/urls.py`, and `tests/test_auth.py` (11 cases). Fixed `ApiError` to set `self.status_code`.
- Verified (commands + result):
  - `./tasks.ps1 verify` -> ruff "All checks passed", format "70 files already formatted", mypy "Success" x3, pytest 11 + 25 + 5 passed.
  - Live on :3001 (`curl.exe --data-binary @file`): register 201 (token has `sub`/`role`/`iss`), duplicate 409 `EMAIL_ALREADY_EXISTS`, login 200, `/me` 200, bad login 401 `INVALID_CREDENTIALS`.
  - `uv run python manage.py spectacular --validate --fail-on-warn` -> exit 0 (no schema warnings).
- Not done / left half-way: job command endpoints (create DRAFT, update, publish, close) + state machine, `withTx`, outbox inserts on publish/update-while-published/close, recruiter list, public `GET /jobs/:id`. Dev JWT keypair generated and written to the git-ignored `.env`; `.env.example` keeps empty placeholders.
- Gotchas/decisions added: `ApiError` must set `self.status_code` (DRF uses the instance attr, not `code`); SimpleJWT `USER_ID_CLAIM` is `user_id` by default (set to `sub`); ES256 needs `cryptography`; test settings generate an ephemeral keypair; PowerShell mangles inline curl JSON (use `--data-binary @file`); ruff RUF012 false positives in serializers/views ignored.
- Next session should start with: M2 job commands in `apps/jobs` (serializers + services + `withTx` in the same transaction as the outbox insert), state machine `DRAFT->PUBLISHED->CLOSED`, ownership 404, `version` bump on every write, and the M2 acceptance tests (rollback leaves no outbox row and no job change; draft edits emit nothing).

### Session 4: 2026-10-19: M2 (job commands) — M2 COMPLETE
- Did: implemented the job lifecycle in job-service: `apps/jobs/{serializers,services,views,urls}.py`, `apps/core/db.py` (`with_tx`), `apps/core/permissions.py` (`IsRecruiter`), `apps/outbox/services.py` (`enqueue_job_event` builds the `contracts` envelope + full snapshot). State machine `DRAFT->PUBLISHED->CLOSED` with `select_for_update` + `version+1` per write; publish/published-update/close write the outbox row in the same transaction; draft edits emit nothing. Routes: `POST|GET /recruiter/jobs`, `GET|PUT /recruiter/jobs/:id`, `POST /recruiter/jobs/:id/publish`, `POST /recruiter/jobs/:id/close`, public `GET /jobs/:id`. Tests `tests/test_jobs.py` (13 cases).
- Verified (commands + result):
  - `./tasks.ps1 verify` -> ruff "All checks passed", format "78 files already formatted", mypy "Success" x3, pytest 11 + 38 + 5 passed.
  - `uv run python manage.py spectacular --validate --fail-on-warn` -> exit 0.
  - Live on :3001 (`curl.exe`): create 201 DRAFT v1, list 200 total=1, public draft 404, publish 200 PUBLISHED v2, double publish 409 `INVALID_STATE_TRANSITION`, edit published 200 v3, close 200 CLOSED v4, public closed 404, edit closed 409.
  - `manage.py shell` -> outbox rows `[('JobPublished',2), ('JobUpdated',3), ('JobClosed',4)]`, all `published_at=None` (relay is M3); no row for the draft edit.
- Not done / left half-way: M3 onward (Kafka client, relay, `/internal/admin/outbox`). Nothing half-written in M2.
- Gotchas/decisions added: stale `runserver` processes hold port 3001 (kill the listening pid in a loop); `IsRecruiter` reads `request.auth`, so tests need a real Bearer token; outbox `payload` stores the full envelope JSON.
- Next session should start with: M3 — `confluent-kafka` client with lazy/background connect + retry, `ensureTopics`, idempotent producer (`acks=all`, key=aggregateId), the relay loop (advisory lock, `FOR UPDATE SKIP LOCKED`, ordered, backoff, `OUTBOX_RELAY_ENABLED`), `GET /internal/admin/outbox`, `/readyz` Kafka status.

### Session 5: 2026-10-19: M3 (outbox relay + producer) — M3 COMPLETE
- Did: implemented M3 in job-service: `apps/core/kafka.py` (`KafkaClient`, `status: unknown|up|degraded`, `ensure_ready`, monitor thread, idempotent producer `acks=all`, topics `jobs.events.v1` x3 + `.dlq` x1), `apps/core/internal.py` (`X-Internal-Token`, `hmac.compare_digest`), `apps/outbox/relay.py` (advisory lock `4242001`, `select_for_update(skip_locked=True)`, ordered, backoff cap 30 s, stop batch on first failure), `apps/outbox/management/commands/run_relay.py` (monitor-driven; publishes only while `status == "up"`; graceful SIGINT/SIGTERM), `apps/outbox/views.py` + `urls.py` (`GET /internal/admin/outbox`), `apps/core/views.py` (`/readyz` reports kafka status), settings (`KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_MONITOR_ENABLED`, `KAFKA_MESSAGE_TIMEOUT_MS`, `OUTBOX_RELAY_ENABLED`, `INTERNAL_TOKEN`), `contracts` header constants, `tests/test_relay.py` (6) + `tests/test_internal.py` (5).
- Verified (commands + result):
  - `./tasks.ps1 verify` -> ruff "All checks passed", format "88 files already formatted", mypy "Success" x3, pytest 11 + 49 + 5 = 65 passed.
  - Topics live: `kafka-topics.sh --describe` -> `jobs.events.v1` PartitionCount 3, RF 1; `jobs.events.v1.dlq` PartitionCount 1.
  - Happy path live: create + publish -> HTTP 201/200, outbox `{pending:0, publishedLastHour:4}`.
  - Outage live: `docker compose ... stop kafka` -> publish HTTP 200 -> outbox `{pending:1, lastError:"1 message(s) not delivered before timeout"}` -> `start kafka` -> pending 1 -> 1 -> 0 within ~10 s -> final `{pending:0, publishedLastHour:5}`.
- Not done / left half-way: nothing half-written. M4 not started.
- Gotchas/decisions added: AdminClient GC (`_DESTROY`, `UNKNOWN_TOPIC_OR_PART`) -> persistent `self._admin_client`; relay gates on monitor `status == "up"` to avoid per-row 5 s flush timeout while Kafka is down; duplicate `run_relay`/`runserver` python pids when scripting (`uv` parent + child). Decision: relay publishes only while status is `up`.
- Next session should start with: M4 — Candidate Service migrations (`candidates`, `jobs` replica, `applications` with `UNIQUE (candidate_id, job_id)`, `processed_events`), candidate auth, and the consumer (`processed_events` insert + version-guarded upsert in ONE tx, 3 retries with backoff, non-retryable -> DLQ, offset after DLQ publish).
