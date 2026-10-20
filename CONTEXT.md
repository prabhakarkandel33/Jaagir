# CONTEXT.md

Living project memory and **the work queue**. Every session reads this first and updates it last (rules in AGENTS.md §1). Write for a stranger with zero memory.

**Sections:** 1 Status board · 2 Session plan · 3 Milestones · 4 Gotchas · 5 Decisions · 6 Blocked / needs human · 7 Session log

---

## 1. Status board

```
Current milestone : M7A
State             : IN PROGRESS (Phase 1 backend DONE 2026-10-20; Phase 2 frontend foundation NEXT)
Last session      : S13 (2026-10-20, Phase 1 backend)
Next action       : Phase 2 frontend foundation: react-router-dom, lib/session.tsx, PublicShell/PortalShell, guards, signed-in redirects, real /jobs/:id page
Last green verify : 2026-10-20 (ruff clean, format 150 files, mypy x3 Success, pytest 11 + 89 + 78 = 178)
Last green e2e    : 2026-10-20 (5/5 scenarios, four consecutive green runs)
Frontend          : three surfaces: public site (warm paper), signed-in recruiter/candidate portals (same warm tokens, sidebar/tabs), `/admin` ops console (dark); react-router-dom with session guards and silent refresh; CV upload/preview; 1440 + 500 px screenshots in `docs/screenshots/`; containerized on :5174 (nginx-unprivileged), `npm run build` clean

Progress: `[~] M0  [x] M1  [x] M2  [x] M3  [x] M4  [x] M5  [x] M6  [x] M7A  [ ] M7  [ ] M8  [ ] M9`

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
| S12 | M7A | Portal overhaul, human-requested (2-3 sessions; backend first, then frontend) |
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
- [x] Migrations: `candidates`, `jobs` (replica), `applications` (with `UNIQUE (candidate_id, job_id)`), `processed_events`.
  - [2026-10-19] Done in candidate-service: `apps/candidates/models.py` (custom `AUTH_USER_MODEL`), `apps/jobs/models.py` (replica + `JobStatus`/`EmploymentType`, check constraints, indexes), `apps/applications/models.py` (`UniqueConstraint` on `(candidate, job)`), `apps/events/models.py` (`ProcessedEvent` + `ConsumerStatus` heartbeat). Migrations 0001 x4 + `events.0002_consumerstatus` applied to `candidate_db`.
- [x] Candidate register/login/profile (candidate-issued JWT; also loads Job Service **public key** from env for recruiter tokens).
  - [2026-10-19] `apps/candidates/{serializers,services,views,urls}.py`, `apps/core/authentication.py` (`IssuerAwareJWTAuthentication` picks the verifying key from the token `iss`), `apps/core/throttling.py`, `apps/core/permissions.py`. Live: register 201 (token `role=candidate`, `iss=candidate-service`), login 200, duplicate 409.
- [x] Consumer per §6.2: one DB tx (inbox insert + version-guarded upsert), 3 retries with backoff for transient errors, non-retryable -> DLQ immediately, DLQ headers, offset committed after DLQ publish. One shared `upsertJobFromSnapshot()` function (reused by M6).
  - [2026-10-19] `apps/events/{services,consumer}.py`, `apps/jobs/{repo,services}.py` (`upsert_job_from_snapshot`, `ON CONFLICT (id) DO UPDATE ... WHERE jobs.version < EXCLUDED.version`), `management/commands/consume_events.py`. Tests in `tests/test_consumer.py` (7): duplicate -> one row/one `processed_events`, v3-then-v2 stays v3, JobClosed, poison -> DLQ + next message applies, transient retry, shared upsert. Live: consumer replayed the M3 backlog `fromBeginning` and applied every event once.
- [x] Boot independent of Kafka (I9); `/readyz` shows consumer state.
  - [2026-10-19] `apps/core/views.py` `readyz` reports `consumer`/`kafka` from the `consumer_status` heartbeat row (`up|degraded|stale|unknown`, `disabled` when `KAFKA_CONSUMER_ENABLED=False`) and never fails readiness. Live with Kafka down: `GET /healthz` 200 and `/readyz` `status: ok`. Live with Kafka up: `{"consumer":"up","kafka":"up"}`. Tests `tests/test_health.py` (6).
- [x] Apply: job must exist locally and be `PUBLISHED` (else 404 `JOB_NOT_FOUND` / 409 `JOB_NOT_OPEN`); duplicate -> 409 `APPLICATION_ALREADY_EXISTS` via SQLSTATE 23505 (no check-then-insert race); store title/company snapshot.
  - [2026-10-19] `apps/applications/services.py` + `views.py`. Live against the replica: apply 201 (snapshots filled), duplicate 409 `APPLICATION_ALREADY_EXISTS`, after close 409 `JOB_NOT_OPEN`. Test: 10 concurrent applies -> 1 created, 9 conflict, 1 row.
- [x] `GET /candidates/me/applications` (paginated, newest first, includes status) + detail.
  - [2026-10-19] `apps/applications/views.py` (`CandidateApplicationsView`, `CandidateApplicationDetailView`); live history returns `total: 1`.
- [x] `GET /recruiter/jobs/:jobId/applications` (recruiter JWT from Job Service; ownership via replica `recruiter_id`; paginated). `(P1)` `PATCH /recruiter/applications/:id/status`. `(P1)` sync fallback `GET /internal/jobs/:id` when a job is missing locally (timeout 2 s; never blocks when Job Service is down).
  - [2026-10-19] Done: `RecruiterJobApplicationsView` verifies the Job-Service-issued token with the peer public key and checks `jobs.recruiter_id`. Live: owner sees `total: 1`; another recruiter -> 404 `JOB_NOT_FOUND`. **P1 items NOT done** (status PATCH, sync fallback).
- **Acceptance (tests):** same event delivered twice -> one row, one `processed_events`; v3 then v2 -> stays v3; JobClosed -> apply gives 409 `JOB_NOT_OPEN`; **10 concurrent applies by one candidate -> exactly one 201, nine 409, one row**; malformed message -> lands in DLQ and next message still processes; recruiter B cannot read recruiter A's applications. `make verify` green.

### M5: Search (PostgreSQL FTS)
- [x] Migrations in **both** services (per ARCHITECTURE §7): trigger function + `search_vector`, backfill existing rows, partial GIN on `search_vector`, GIN on `skills`, btree indexes. Down migrations drop them.
  - [2026-10-19] `apps/jobs/migrations/0002_job_search.py` in BOTH services (identical SQL; candidate uses `cjobs_*` index names). Trigger `jobs_search_vector_trg` (`BEFORE INSERT OR UPDATE`, weights A title / B skills+company / C description), then `UPDATE jobs SET search_vector = NULL` to backfill through the trigger, then the indexes. `reverse_sql` drops the trigger and the function. Verified live: `search_vector` = `'acm':6B 'build':7C ... 'senior':1A`, trigger present, all 9 indexes present.
- [x] Query module with `websearch_to_tsquery`, weighted `ts_rank_cd`, tie-breakers, filters (employmentType, location, skills), `page/pageSize`, `total`. Empty query = browse. Endpoints: Job Service `GET /jobs`, Candidate Service `GET /jobs`. Unpublished and closed never returned.
  - [2026-10-19] `apps/jobs/search.py` in both services (SQL strings + `_filter_sql`; `status = 'PUBLISHED'` is a literal so the partial GIN index applies; filters are fixed fragments with bound params; `ORDER BY rank DESC, published_at DESC NULLS LAST, id`). Views `PublicJobSearchView` (:3001) and `JobSearchView` (:3002); `JobSearchParamsSerializer` validates `q`, `employmentType`, `location`, `skills`, `page`, `pageSize` (max 50). Live: `q=python engineer` -> `total: 3707`; `q=kubernetes&employmentType=CONTRACT` -> `total: 1584`; hostile `q` -> 200; bad `employmentType` -> 400.
- [x] `scripts/seed-jobs.ts` (`make seed N=100000`): realistic varied vocabulary from word lists (no heavy deps), ~90% PUBLISHED / 5% CLOSED / 5% DRAFT, inserted in batches. Candidate side is seeded through its own DB path (it is a replica; for benchmark seeding direct insert is allowed inside `scripts/` only).
  - [2026-10-19] Python, not TS: `scripts/seed_jobs.py --service job|candidate --count N` (psycopg3 `cursor.copy()`, 5,000-row batches, word lists, `ANALYZE jobs` at the end). Job mode creates 50 seed recruiters (FK); candidate mode inserts directly. Live: 100,207 rows in ~21 s (job) and 100,205 rows in ~21 s (candidate). Wired to `tasks.ps1 seed -N` and `make seed N=`.
- [x] `scripts/explain-analyze.sh` / `make explain`: runs >= 3 representative queries with `EXPLAIN (ANALYZE, BUFFERS)`, once with indexes disabled/dropped (Seq Scan baseline) and once with them (Bitmap Index Scan on GIN).
  - [2026-10-19] `scripts/explain_analyze.py --service job|candidate`, wired to `tasks.ps1 explain` / `make explain`. Three queries: keyword, keyword+employment type, skills containment. Baseline uses session-level `SET enable_indexscan/enable_bitmapscan = off` (NOT `SET LOCAL`, which is a no-op outside a transaction and silently produced identical plans).
- [x] `docs/search-performance.md`: indexing strategy explained, query shapes, real captured plans and timings, caveats.
  - [2026-10-19] Written with real captured plans at 100k rows. Job Service: Q1 173.256 -> 29.097 ms, Q2 88.122 -> 16.311 ms, Q3 84.783 -> 3.136 ms. Candidate Service: Q1 60.519 -> 24.136 ms, Q2 76.225 -> 18.576 ms, Q3 91.586 -> 2.598 ms. All indexed runs show `Bitmap Index Scan on ..._search_vector_gin` / `..._skills_gin`.
- **Acceptance (tests):** unpublished/closed excluded; title-match outranks description-match; pagination is stable and non-overlapping; weird input (`"`, `'`, `&`, `:*`, empty, 10k chars) never causes 500 and cannot inject SQL. `make explain` output shows GIN usage at 100k rows.
  - [2026-10-19] `job-service/tests/test_search.py` (20 cases) and `candidate-service/tests/test_search.py` (15 cases) cover every acceptance bullet, including `'; DROP TABLE jobs; --` leaving the table intact and an invalid `employmentType` returning 400. `make explain` shows GIN usage at 100k rows (see doc).

### M6: Reconciliation, DLQ replay and outage proof (MOST IMPORTANT) — M6 COMPLETE
- [x] Job Service `GET /internal/jobs/snapshot?after&limit` per §6.3 (non-DRAFT, keyset by id, full payloads, token-guarded).
  - [2026-10-20] `apps/jobs/snapshot.py::to_snapshot()` is the single snapshot builder (the outbox reuses it, so event and endpoint payloads cannot drift). `apps/jobs/internal_views.py`: `InternalJobSnapshotView` (`after` keyset by id, optional `updatedAfter` for the incremental window, `limit` 1..1000 default 500, returns `{items, nextAfter, hasMore}`) and `InternalJobDetailView` (`GET /internal/jobs/<uuid>`, 404 `JOB_NOT_FOUND` for drafts — this also closes the M4 P1 sync-fallback item). `tests/test_internal_snapshot.py` (11 cases: drafts excluded, keyset paging, limit bounds, token guard, detail 404/200). Job service 80 passed.
- [x] Candidate reconciler: full + incremental modes, schedule (30 s after boot, 5 min incremental, nightly full), uses shared `upsertJobFromSnapshot()`, writes `reconcile_runs`, logs anomalies, on-demand `POST /internal/admin/reconcile?mode=`, `GET /internal/admin/sync-status`.
  - [2026-10-20] `apps/events/models.py::ReconcileRun` (+ migration `events.0003_reconcilerun`); `apps/events/job_client.py` (stdlib urllib, `X-Internal-Token`, raises `JobServiceUnavailable`); `apps/events/reconciler.py` (`reconcile(mode)`: 10 min overlap for incremental, one transaction per page, temp table `reconcile_seen` for the full-mode "local row absent from source" anomaly, local-newer-version anomaly WARN, one run row per pass including failures, `sync_status()`); `apps/events/views.py`/`urls.py`; `management/commands/run_reconciler.py` (startup delay, incremental 300 s, full 86400 s, SIGTERM safe); settings `RECONCILE_*`. `tests/test_reconciler.py` (12 cases: repair, idempotent rerun, anomaly never deletes, local-newer WARN, incremental overlap, job-service-down run row, sync-status). Candidate service 57 passed.
- [x] `scripts/replay-dlq.ts` (`--dry-run`, `--limit`) and `POST /internal/admin/dlq/replay`.
  - [2026-10-20] Python, not TS. All replay logic is in `apps/events/dlq.py` (`replay_dlq()`: throwaway group id, never commits, `clean_headers()` strips `dlq-*`, read set = DLQ size at call start). Exposed as `POST /internal/admin/dlq/replay?limit&dryRun` and `manage.py replay_dlq`; `scripts/replay_dlq.py` is a thin HTTP client, so the CLI and the server cannot drift. `tests/test_dlq.py` (3 cases).
- [x] `e2e/` scenarios (automated, `make e2e`) and `scripts/demo-kafka-outage.sh` (same story, human-readable PASS/FAIL narration):
  - **A** Kafka stopped -> publish, update, close jobs -> API OK, outbox pending > 0, candidate replica stale -> Kafka started -> outbox drains, replica matches.
  - **B** Candidate consumer stopped while events flow -> restarted -> catches up from offsets.
  - **C** Simulated lost events (delete replica rows / lower versions directly in `candidate_db`) -> `reconcile` repairs, `repaired` count matches.
  - **D** Poison message on topic -> goes to DLQ, healthy messages keep flowing -> fix cause -> `replay-dlq` -> applied.
  - **E** Topic deleted/recreated (or consumer offsets reset to end) so events are truly gone -> reconcile restores full consistency.
  - Final assertion in every scenario: `(id, version, status)` of all non-draft jobs identical between Job Service snapshot and Candidate replica; no duplicate rows; applications untouched.
  - [2026-10-20] `e2e/run_e2e.py` (all five scenarios, `--scenario`, `--keep`, `--no-build`), wired to `tasks.ps1 e2e` / `make e2e`. Own Compose project `jobportal-e2e` and ports 13001/13002/15433/15434/19092, so it never collides with `make dev`; `down -v` at the start of every run. `scripts/demo_kafka_outage.sh` narrates scenario A and calls the same runner.
- [x] `docs/outage-recovery.md`: scenario descriptions + **captured real output** of the demo script.
  - [2026-10-20] Written with the full captured transcript, timings per scenario, the three-run stability line, and the operations table (outbox backlog, reconcile, sync-status, replay).
- **Acceptance:** `make e2e` all scenarios pass **three runs in a row** (flakiness check); `docs/outage-recovery.md` contains real transcripts. Record any flake root cause in Gotchas.
  - [2026-10-20] Run 1 `5/5 in 110.3s`, run 2 `5/5 in 110.3s`, run 3 `5/5 in 101.8s` (fresh stack each time). A fourth run after BOM/format cleanup: `5/5 in 240.5s` (slower host under load, no functional change). Flake root causes are in Gotchas (docker-exec Kafka helper hang; unbounded DLQ replay loop).

### M7A: Portal overhaul (human-requested, before M7 infra)

Goal: replace the one-page public portals with LinkedIn-style multipage flows, add applicant profiles and CV upload/preview, and keep sessions alive. The public site and `/admin` keep their current design. Resume M7 only after M7A is green.

**Locked decisions (human, 2026-10-20):**
- CV = PDF only, max 5 MB, stored by the Candidate Service. Human-directed exception to ARCHITECTURE.md §13 ("no file uploads", resume URL only); record in Decisions and update §4.2/§10/§13.
- Session = access token 1 h + refresh token 7 days (`POST /auth/{recruiters,candidates}/refresh` in each service).
- Router = `react-router-dom` (nested layouts, params, redirects).
- Recruiters may change applicant status (`IN_REVIEW`, `SHORTLISTED`, `REJECTED`, `ACCEPTED`).
- One active role per browser: signing in as recruiter clears the candidate session and the reverse also holds.
- Signed-in users are redirected away from `/`, `/me`, `/employers` to their dashboard.
- Recruiters see applicant name/email/phone/headline/skills/summary/CV only for candidates who applied to that recruiter's jobs.

**Data + storage (candidate-service):**
- [x] Add `resume_file` (FileField, random `resumes/<uuid>.pdf`), `resume_filename` (sanitized display name), `resume_uploaded_at` to `apps/candidates/models.py`; migration `candidates.0002_*` (new file only; I5).
- [x] `MEDIA_ROOT` from env (dev: `<service>/media`, git-ignored); `RESUME_MAX_BYTES=5242880`; add `.env.example` entries.
- [x] Validate PDF magic (`%PDF-`), non-empty, size <= 5 MiB -> 400 `INVALID_RESUME_FILE` / `RESUME_TOO_LARGE`; store random filename, delete the old file on replace/remove.
- [x] Never serve media via `MEDIA_URL`; use guarded `FileResponse` with `application/pdf`, `X-Content-Type-Options: nosniff`, `Content-Disposition: attachment`.
  - [2026-10-20, S13] `apps/candidates/models.py::resume_upload_path` (uuid name), migration `candidates.0002_resume_file` applied to `candidate_db`; `MEDIA_ROOT`/`RESUME_MAX_BYTES` in `config/env.py` + settings; media dirs are git-ignored by the existing `media/` rule. `apps/candidates/resume.py` validates size/magic, stores the sanitized display name, deletes replaced/removed files, and streams `FileResponse` with `nosniff` + `attachment`. Empty uploads stay `INVALID_RESUME_FILE` (`allow_empty_file=True` in the serializer); oversized uploads return `RESUME_TOO_LARGE`. Live smoke on :3002: upload 200 `has_resume=true`, download 200 `%PDF-` with the expected headers, refresh 200.

**Backend endpoints (all with `extend_schema`, OpenAPI clean):**
- [x] Job: `GET /recruiter/dashboard` -> `{jobs:{total,byStatus},recentJobs}`.
- [x] Job: `POST /auth/recruiters/refresh` (own signing key; access carries `role`/`iss`).
- [x] Candidate: `GET /candidates/me/dashboard` -> `{applications:{total,byStatus},recent}`.
- [x] Candidate: `GET /recruiter/dashboard` -> `{applications:{total,byStatus,newCount},recent}` (recruiter token; all owned jobs).
- [x] Candidate: `GET /recruiter/application-counts` -> `[{jobId,total,byStatus}]` for the recruiter's roles.
- [x] Candidate: `GET /recruiter/applications/:id` -> application + nested candidate profile + job snapshot + CV flags; 404 for other recruiters.
- [x] Candidate: `PATCH /recruiter/applications/:id/status` -> validate allowed statuses, ownership via `job.recruiter_id`, bump `status_updated_at`.
- [x] Candidate: `GET /recruiter/applications/:id/resume` -> guarded PDF; 404 when missing/foreign.
- [x] Candidate: `POST|DELETE /candidates/me/resume` (multipart `file`), `GET /candidates/me/resume`.
- [x] Candidate: `POST /auth/candidates/refresh`.
- [x] Extend `GET /recruiter/jobs/:jobId/applications` with nested candidate summary (`id, full_name, email, phone, headline, location, skills, summary, resume_url, resume_filename, has_resume`). Keep candidate history serializer lean.
- [x] Keep dashboards single-DB (I1); counts use `values().annotate(Count(...))`, no cross-service SQL.
  - [2026-10-20, S13] `apps/jobs/{services,serializers,views}.py` (Job dashboard), `apps/recruiters/{services,views,urls}.py` (refresh), `apps/applications/{services,serializers,views,urls}.py` (candidate/recruiter dashboards, all-applicants list, per-role counts, applicant detail, status PATCH, guarded resume). Auth responses now also return `refresh` + `refreshExpiresIn`; `SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = 7 days` in both services. `GET /recruiter/application-counts` is a top-level route (not under `/applications`). Foreign applications always 404 `APPLICATION_NOT_FOUND`.

**Tests (mandatory):**
- [x] Upload: valid PDF accepted; non-PDF rejected; > 5 MiB rejected; replace deletes old file; delete clears fields.
- [x] Download: candidate self OK; recruiter only for own applicant; other recruiter 404; anonymous 401.
- [x] Applicant detail/status: ownership, allowed/blocked statuses, timestamp bump.
- [x] Dashboard counts (jobs by status, applications by status, per-role counts) match fixtures.
- [x] Recruiter list exposes candidate name/CV flag; candidate history does not expose another candidate.
- [x] Refresh: valid token returns access with `role`/`iss`; wrong-service token rejected.
- [x] Existing reliability suites stay green.
  - [2026-10-20, S13] New `candidate-service/tests/test_resume.py` (11), `tests/test_recruiter_portal.py` (6), `tests/test_auth.py` refresh cases (2); `job-service/tests/test_dashboard.py` (2), `tests/test_auth.py` refresh cases (2). `./tasks.ps1 verify` -> ruff clean, format 150 files, mypy Success x3, pytest 11 + 89 + 78 = 178. Both `spectacular --validate --fail-on-warn` exit 0.

**Frontend routes:**
- Public: `/`, `/jobs`, `/jobs/:id` (real job page), `/employers` (auth), `/me` (auth).
- Recruiter: `/employers/dashboard`, `/employers/profile`, `/employers/post`, `/employers/roles`, `/employers/roles/:id`, `/employers/roles/:id/edit`, `/employers/applicants`, `/employers/applicants/:applicationId`.
- Candidate: `/me/dashboard`, `/me/profile`, `/me/applications`, `/me/applications/:id`.
- [x] Add `react-router-dom`; `layouts/PublicShell.tsx` + `layouts/PortalShell.tsx` (sidebar/tabs, account menu, sign out).
- [x] `lib/session.tsx`: access+refresh storage, refresh once on 401, cross-tab `storage` sync, sign-out, `?next=` redirects, guards (`RequireRecruiter`, `RequireCandidate`).
- [x] Recruiter pages: dashboard stats + recent applicants; company profile; post role (save draft / publish now); roles list with per-role applicant counts; role detail + applicants; role edit; applicant detail with profile, cover letter, CV preview/download, status select.
- [x] Candidate pages: dashboard (status counts, profile completeness, recent applications, recent roles); profile with CV upload/replace/remove/preview; applications list; application detail.
- [x] Public: signed-in header shows Dashboard + Sign out; root `/` redirects by active role; `/me` and `/employers` redirect when already signed in.
- [x] `Discover`: "View role" navigates to `/jobs/:id`; keep debounce/applied-filters/URL sync; job page applies with sign-in return.
- [x] Split CSS: keep `public.css` for public/auth; add `portal.css` for the signed-in product (same warm tokens, not the admin theme).
- [x] Responsive: sidebar -> tabs below 980 px; tables -> cards below 760 px; empty/error/loading states on every page.
  - [2026-10-20, S14] All routes live on `:5174`: `App.tsx` uses pathless `RequireRole` + `PortalShell` layout routes with explicit children (a splat route outranked the exact `/employers`/`/me` sign-in routes and looped `?next=`). `lib/session.tsx` stores `jp.session`, single-flight refresh via `setTokenRefresher`, `storage` listener, `safeNext`. `npm run build` clean (73 modules, 349.8 kB JS / 46.6 kB CSS). Playwright walkthrough passed: guards, publish, apply, CV upload, status change, CV download, silent refresh, 500 px no overflow.

**Acceptance:**
- [x] `./tasks.ps1 verify` green (new backend tests included), migrations applied on both DBs, OpenAPI validation clean.
  - [2026-10-20, S13] Verified. Phase 2/3 frontend acceptance items below are still open.
- [x] `npm run build` clean; container rebuilt and healthy on `:5174`.
- [x] Manual: recruiter register -> profile -> post -> publish -> candidate search -> upload CV -> apply -> recruiter dashboard counts -> role applicants show name -> applicant profile + CV -> status change -> candidate sees new status.
- [x] Session: reload stays signed in; `/` and `/me`/`/employers` redirect correctly; expired access refreshes silently; sign out clears both tokens.
- [x] Screenshots at 1440 px and 500 px for each portal page; no overflow; README updated.
- [x] `make e2e` still 5/5 (reliability paths untouched).
- [x] ARCHITECTURE.md updated (§4.2 fields, §8 endpoints, §10 media volume/backup, §13 exception); Decisions + Session log appended.
  - [2026-10-20, S14] `npm run build` clean (73 modules, 349.8 kB JS / 46.6 kB CSS); `docker compose build frontend` + `up -d frontend` -> `(healthy)` on `:5174`.
  - [2026-10-20, S14] Playwright (`uv run --no-project --with playwright`, bundled chromium) ran the whole flow with `rina.1792484373@example.com` / `aarav.1792484373@example.com` (`PortalCheck123!`): publish, apply, CV upload + download (`%PDF-`), applicant detail, status -> `SHORTLISTED` (candidate sees it), silent refresh (access token corrupted, `wait_for_function` proved a new one), reload persistence, signed-out redirects, sign-out, 500 px no overflow.
  - [2026-10-20, S14] 16 portal screenshots at 1440 px + 500 px in `docs/screenshots/`; README "Signed-in portals" section added.
  - [2026-10-20, S14] `./tasks.ps1 verify` -> ruff clean, format 150 files, mypy Success x3, pytest 11 + 89 + 78 = 178. `./tasks.ps1 e2e` -> `5/5 scenarios passed in 207.0s`; final assertion `8 non-draft jobs identical in both databases`. E2E now publishes the frontend on `:15174` so it coexists with the dev stack on `:5174`.

**Out of scope:** DOCX uploads, virus scanning, saved jobs, messaging, email notifications, S3/object storage.

### M7: Containerization and CI/CD
- [x] Frontend image: `frontend/Dockerfile` (multi-stage `node:22-slim` build -> `nginxinc/nginx-unprivileged:1.27-alpine`, non-root uid 101, port 8080, `/healthz`, `HEALTHCHECK`), `frontend/nginx.conf` (SPA fallback, immutable `/assets` cache, security headers), `frontend/.dockerignore`, and a `frontend` service in `deploy/docker-compose.dev-full.yml` (`:5174`, waits for both web healthchecks).
  - [2026-10-20, S9] `docker compose -f deploy/docker-compose.dev-full.yml up -d --build frontend` -> container healthy; `curl.exe http://localhost:5174/healthz` -> 200 `ok`; `/` and `/ops` -> 200 (SPA fallback); screenshot of `:5174` matches the dev design and shows live search results. API bases are Vite build args (`VITE_JOB_SERVICE_URL`, `VITE_CANDIDATE_SERVICE_URL`), so changing them needs an image rebuild.
- [x] Two-world UI (human-requested): public site (`/`, `/jobs`, `/employers`, `/me`) in a warm paper theme with plain language, larger type, and a landing page; technical ops console at `/admin` on the existing dark theme, signed in with `ADMIN_USERNAME`/`ADMIN_PASSWORD` from each service `.env` via `POST /internal/admin/login`. Path routing replaces hash tabs; every page is served by the nginx container on `:5174`.
  - [2026-10-20, S10] `npm run build` clean (41 modules). Live on `:5174`: `/`, `/jobs`, `/employers`, `/me`, `/admin` -> 200; `POST :3001/internal/admin/login` and `:3002/...` return `{service, token}`; wrong credentials -> 401. Headless Edge screenshots at 1440 px and 500 px: landing, jobs (209,168 live results), employer sign-in, candidate sign-in, admin sign-in. `./tasks.ps1 verify` -> ruff clean, format 145 files, mypy x3, pytest 11 + 85 + 60 = 156.

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

- [2026-10-19, M4] The consumer runs in its OWN process (`manage.py consume_events`), so an in-process `get_event_consumer()` cache is invisible to the web process. Symptom: `/readyz` stuck at `consumer: unknown` even while the consumer logs `status up`. Fix: the consumer upserts a single `consumer_status` row (status, last_error, processed, dlq_count, last_heartbeat_at) on every status change, on each handled message and on each idle poll; `readyz` reads that row and reports `up|degraded|stale|unknown` (stale after 15 s without a heartbeat). Rule: any cross-process state must go through the DB, never a module-level cache.
- [2026-10-19, M4] `manage.py runserver --noreload` keeps serving the OLD code after a file edit, so a fixed `readyz` still answered with the old logic and looked broken. Symptom: an edit did not change the live response. Fix: restart the listener (`Get-NetTCPConnection -LocalPort 3002 -State Listen` -> `Stop-Process`) after editing views/settings.
- [2026-10-19, M4] `confluent_kafka` stubs type `Message.headers()` as `Union[Dict[str, ...], List[Tuple[str, ...]]]`, so `for k, v in msg.headers()` is `str-unpack` to mypy (dict keys are strings) and `produce(headers=...)` rejects `list[tuple[str, bytes]]` (parameter is invariant). Fix: `cast("list[tuple[str, str | bytes | None]]", msg.headers() or [])` into a `list[tuple[str, str | bytes | None]]`.
- [2026-10-19, M4] SimpleJWT `Token.verify()` raises `TokenError("Token has no id")` when the `jti` claim is absent, which surfaces as a 401 `INVALID_TOKEN` on the peer service. Fix: mint test/peer tokens with an explicit `jti` (the real SimpleJWT flow always sets one).
- [2026-10-19, M4] Do NOT hand an empty verifying key to a SimpleJWT `TokenBackend`: ES256 decode fails and every token looks invalid. Fix: read the (unverified) `iss` with `PyJWT.decode(..., options={"verify_signature": False})` first, then select the key (`candidate-service` -> own signing key; `job-service` -> `JOB_SERVICE_JWT_PUBLIC_KEY`).
- [2026-10-19, M4] The candidate dev box needed its own ES256 keypair plus the Job Service **public** key: `candidate-service/.env` (`JWT_SIGNING_KEY`, `JWT_PUBLIC_KEY`, `JOB_SERVICE_JWT_PUBLIC_KEY`) is git-ignored; generate with `uv run python -c "..."` (base64 PEM) and copy the job-service public key across.
- [2026-10-19, M4] The candidate replica detail endpoint (`GET /jobs/:id`) returns 404 for a CLOSED job by design, but the local row still exists with `status='CLOSED'` — that is why applying after close gives 409 `JOB_NOT_OPEN` (not 404). Do not "fix" the 404 by exposing closed jobs.
- [2026-10-19, M4] Do not poll a start-up loop with an unbounded `for` body that contains blocking `Invoke-WebRequest` calls: 60 iterations x (0.5 s + 2 x 2 s timeouts) can exceed the tool timeout and the terminal then looks hung. Use `curl.exe -m 2`, a small iteration count, and print the result.
- [2026-10-19, M7 (done early, dev only)] One-command local stack: `deploy/docker-compose.dev-full.yml` uses Compose `include:` (needs Compose >= 2.20; local is v5.1.4) to pull in `docker-compose.dev.yml`, so kafka/job-db/candidate-db keep their fixed `container_name`s and volumes and are shared with `infra-up`. Run: `./tasks.ps1 stack-up -Build` then `stack-ps` / `stack-logs` / `stack-down` (`make stack-up BUILD=1` on Linux).
- [2026-10-19, M7 (dev only)] Bind-mount ONLY the service directory and `packages/` (e.g. `../backend/services/job-service:/app/services/job-service`). Never bind-mount all of `backend/`, because that would hide the image's `/app/.venv` behind the Windows venv. Rebuild the image only when `pyproject.toml`/`uv.lock` change (`uv sync --all-packages --frozen` runs at build time).
- [2026-10-19, M7 (dev only)] The dev image is ONE shared image (`backend/Dockerfile.dev`, context `backend/`) for all containers; each service only differs by `working_dir` + `command` (`runserver` | `run_relay` | `consume_events`). Compose healthchecks use `python -c "import urllib.request..."` because `python:3.12-slim` has no `curl`. Migrations are one-shot services; the web/consumer services wait with `depends_on: ... condition: service_completed_successfully`.
- [2026-10-19, M7 (dev only)] Do not pass `--wait` to `docker compose up` for this file: the one-shot migrate containers exit, and the wait condition then never settles. Start with `up -d` and poll `/readyz` instead.
- [2026-10-19, M5] The trigger backfill must be `UPDATE jobs SET search_vector = NULL`, NOT `UPDATE ... SET search_vector = to_tsvector(...)`. Assigning NULL still fires the `BEFORE UPDATE` trigger, so the expression lives in exactly one place and cannot drift between the migration and the trigger.
- [2026-10-19, M5] `SET LOCAL enable_indexscan = off` is a no-op outside a transaction, so the "baseline" run silently produced the SAME plan as the indexed run. Symptom: two identical plans with the same timing. Fix: session-level `SET` plus an explicit `RESET` after each query (`scripts/explain_analyze.py`).
- [2026-10-19, M5] psycopg3 has no `copy_expert`: use `with cursor.copy("COPY jobs (...) FROM STDIN") as copy: copy.write(text)`. Also, `auto_now`/`auto_now_add` are ORM-only and have NO database default, so a raw COPY must supply `synced_at`/`created_at`/`updated_at` or it fails on NOT NULL.
- [2026-10-19, M5] The `jobs` table columns differ between the two databases (the replica has `source_updated_at`/`synced_at`, the source has `created_at`). The seed script reads `information_schema.columns` and COPYs only the intersection, instead of hardcoding a per-service column list.
- [2026-10-19, M5] Browse ordering MUST be `published_at DESC NULLS LAST`. Plain `DESC` puts NULLs first in PostgreSQL, so rows whose `published_at` was never stamped (tests, manual inserts) jumped to the top of the browse page and the "newest first" test failed.
- [2026-10-19, M5] At ~200 rows the planner picks a Seq Scan even with the GIN index present (correctly). Any EXPLAIN demonstration must run at 100k rows plus `ANALYZE jobs`, or it proves nothing.
- [2026-10-20, M6] `create_job`/`update_job` in `apps/jobs/services.py` take snake_case dicts, and `JobWriteSerializer` (PUT) requires every field. A partial `{"title": ...}` update returns 400 `VALIDATION_ERROR`. The e2e helper now re-sends the full body.
- [2026-10-20, M6] psycopg `cursor.executemany(sql, rows)` needs tuples: a bare `UUID` row raises `TypeError: object of type 'UUID' has no len()`. Rows must be `(uuid,)`.
- [2026-10-20, M6] Full-mode reconciliation needs "which local ids were not in the source" over 100k+ ids; an `IN (...)` list grows past the parameter limit. Fix: temp table `reconcile_seen` + `INSERT ... VALUES %s` per page + `EXCEPT`. `ON COMMIT DELETE ROWS` would wipe it at each page commit, so use `PRESERVE ROWS` and an explicit `DROP` at the end.
- [2026-10-20, M6] `subprocess.run(["docker","exec","-i",kafka,"kafka-console-producer.sh" ...])` and `kafka-topics.sh --delete` hang until the subprocess timeout on this Windows box (30 s and 60 s observed). Fix: drive Kafka from the test host with `confluent-kafka` (`Producer`, `AdminClient`, `get_watermark_offsets`) instead of `docker exec`.
- [2026-10-20, M6] Replaying a still-invalid DLQ message is a feedback loop: replay re-publishes it to `jobs.events.v1`, the consumer rejects it back to the DLQ, the replay consumer (no commits, earliest) reads it again. Observed `read=1000 published=1000` with 2 real messages. Fix: snapshot the DLQ high-watermarks at call start and read at most `min(limit, snapshot)`.
- [2026-10-20, M6] PowerShell `Set-Content -Encoding UTF8` (5.1) writes a BOM. Symptoms: `ruff format` panics with `Annotation range 0..1833 is beyond the end of buffer 1829`, and mypy reports `pyproject.toml: Invalid statement (at line 1, column 1)`. Fix: strip the first 3 bytes, or use the `write`/`edit` tools.
- [2026-10-20, M6] An e2e helper that defaults every path to the candidate base sent `/internal/admin/outbox` to :13002 -> 404. Keep an explicit `base=` defaulting to the job service; pass `base=CAND_URL` only for candidate admin calls.
- [2026-10-20, M6] Scenario A must restore Kafka in a `finally` block. Without it, a failed assertion left the broker stopped (`Exited (137)`) and every later scenario failed for an unrelated reason.
- [2026-10-20, M7] Headless Edge on Windows clamps the CSS viewport to roughly 486-500 px: `--window-size=390` renders ~486 and crops the screenshot, so a "mobile" screenshot proves nothing. Measure `document.documentElement.scrollWidth` through a temporary injected script and `--dump-dom` instead.
- [2026-10-20, M7] PowerShell 5.1 text round-trips damage non-ASCII content: `Set-Content -Encoding UTF8` adds a BOM (ruff then panics, see M6), and `Get-Content` without `-Encoding UTF8` shows UTF-8 as mojibake. Use the `write`/`edit` tools, or `[System.IO.File]::ReadAllText/WriteAllText` with `New-Object System.Text.UTF8Encoding($false)`.
- [2026-10-20, M7] The `write` tool keeps an existing BOM when it rewrites a file (`frontend/index.html` stayed EF BB BF). Strip the first three bytes after a rewrite, or check with `[System.IO.File]::ReadAllBytes`.
- [2026-10-20, M7] .NET file APIs in the shell resolve relative paths against the tool `workdir`, so `[IO.File]::ReadAllText('frontend/src/x')` with `workdir=frontend` looks in `frontend/frontend/`. Pass absolute paths.
- [2026-10-20, M7] The frontend Devanagari stack (`"Noto Serif Devanagari", "Nirmala UI", Mangal, ...`) renders in Nirmala UI (sans) on this Windows box because only `Nirmala.ttc` is installed. The wordmark therefore looks different per OS; bundling one font file is the only way to keep it stable.
- [2026-10-20, M7] `nginxinc/nginx-unprivileged` listens on **8080**, not 80, and runs as uid 101; publish `8080` and keep `USER 101`. Its Alpine base has BusyBox `wget`, so the `HEALTHCHECK` uses `wget`, not `curl`.
- [2026-10-20, M7] Vite inlines `import.meta.env` at build time, so the frontend image is environment-specific: change `VITE_*` build args and rebuild. Do not expect runtime env vars in the container to change the API base.
- [2026-10-20, M7] Running `docker compose` from a new file changes the default project name to the directory name (`jaagir`), which silently creates NEW containers and NEW named volumes: the 100k seeded rows and all users appear lost. Fix: pin `name: ${COMPOSE_PROJECT_NAME:-jobportal-dev}` in the root file, or pass `-p jobportal-dev`. Always compare `docker compose ls` before and after a compose refactor.
- [2026-10-20, M7] A top-level `include:` file does not inherit `name:` from the included file; the including file's directory decides it (see above). `name:` in the root file does win over the included file's `name:`.
- [2026-10-20, M7] `AuthRateThrottle` extended `ScopedRateThrottle` with `scope = "auth"`, but DRF overwrites the scope from `view.throttle_scope`; with no `throttle_scope` on the view it returned `True` and auth routes were never throttled. Fix: subclass `SimpleRateThrottle` and implement `get_cache_key` (user pk or client IP). Both services now do this.
- [2026-10-20, M7] Headless Edge screenshots catch CSS entry animations mid-fade: the hero title looked low-contrast because `opacity: 0` was still animating. Add `--virtual-time-budget=6000` to let fetches and animations settle before the shot.
- [2026-10-20, M7] The admin sign-in calls BOTH services in one `Promise.all`; if the two `.env` files hold different `ADMIN_PASSWORD` values, one call returns 401 and the whole sign-in fails. Keep `ADMIN_USERNAME`/`ADMIN_PASSWORD` identical locally. The returned token is the service's `INTERNAL_TOKEN`.
- [2026-10-20, M7] An old Vite dev server kept port 5173 open. The shipped portal publishes the nginx container on **5174** (user's chosen port) and needs no host Node process; kill stray dev servers before blaming the container.
- [2026-10-20, M7] The job list label showed the new query against the old totals (`209,168 roles for "python"` while typing). Cause: the label read the draft input but the list still held the previous response. Fix: `applied` filters state set at request start + a request sequence guard, and a 350 ms debounce so typing feels live but every count matches its rows.
- [2026-10-20, M7] The role detail rendered after the list and pager, so "View role" forced a long scroll. Fix: two-column results grid with a sticky detail panel above 980 px, and `scrollIntoView` on selection below it.
- [2026-10-20, M7] Back-to-back headless Edge `--screenshot` launches reuse the default profile; the second and later writes silently produce no file. Fix: give each capture a unique `--user-data-dir` and pause briefly between runs. Screenshots live in `docs/screenshots/`; capture sign-in screens only, never a signed-in session with tokens or personal data.
- [2026-10-20, M7A] `manage.py spectacular --validate --fail-on-warn` was red for reasons unrelated to M7A: `/jobs` vs `/jobs/:id` both derived `jobs_retrieve`; the `status` enum collided between jobs and applications; the candidate service's custom `IssuerAwareJWTAuthentication` had no OpenAPI security extension; and the two internal admin POSTs declare only query parameters. Fixes: explicit `operation_id="jobs_search"`/`"jobs_detail"`; `ENUM_NAME_OVERRIDES` in both settings; `apps/core/schema.py` extension registered from `CoreConfig.ready`; `request=None` on those POST decorators.
- [2026-10-20, M7A] DRF's `FileField` rejects an empty upload during serializer validation, so the view never reaches the domain check and returns `VALIDATION_ERROR`. Fix: `FileField(allow_empty_file=True)`; `resume.validate_pdf` then returns the contract code `INVALID_RESUME_FILE`.
- [2026-10-20, M7A] Ruff `SIM115` wants a context manager around `open(path, "rb")` for `FileResponse`, but a `with` block would close the file before the response streams. Keep the open handle (FileResponse closes it) and mark the line `# noqa: SIM115`.
- [2026-10-20, M7A] React Router v7 ranks a splat (`employers/*`) above the exact `/employers` sign-in route, so `RequireRole` bounced `/employers` -> `/employers?next=...` -> `/employers` forever (blank page, growing query string). Fix: use pathless layout routes with explicit child paths; never mix a splat and an exact auth route at the same prefix.
- [2026-10-20, M7A] `signOut()` followed by `navigate("/")` loses the race with `RequireRole` and lands back on the sign-in page. Fix: `signOut(); window.location.replace("/")` in `PortalShell` (full reload also drops in-memory state).
- [2026-10-20, M7A] A single-column `.portal-shell` grid stretches its auto rows to fill `min-height: 100vh`, so the sticky mobile header grew to ~266 px with a large gap (`gridTemplateRows: 110px 121px`). Fix: `.portal-side { align-self: start; align-content: start }` and `.portal-shell { grid-template-rows: auto minmax(0,1fr); align-content: start }` below 980 px.
- [2026-10-20, M7A] Playwright `channel="msedge"` hangs on this box (no navigation, script timeout); the bundled chromium works: `uv run --no-project --with playwright python script.py` after `playwright install chromium`.
- [2026-10-20, M7A] `make e2e` reuses `docker-compose.dev-full.yml`, which now includes the frontend on `${FRONTEND_PORT:-5174}`; that collides with the dev stack. `e2e/run_e2e.py` now sets `FRONTEND_PORT=15174` and points the Vite build args at `13001`/`13002`.
- [2026-10-20, M7A] Docker Desktop returned `500 Internal Server Error` from `compose stop candidate-reconciler` during e2e scenario E, and two e2e containers disappeared. Cause: transient daemon fault with 21 containers across two projects. Fix: rerun; the full suite passed `5/5 in 207.0s`. Do not treat a single daemon 500 as a code failure.
- [2026-10-20, M7A] `CONTEXT.md` had 756 characters of double-encoded mojibake (`Ãƒâ€šÃ‚Â§`) from earlier PowerShell round-trips. Fixed once with `ftfy.fix_text` (read as UTF-8, write as UTF-8, LF); check with the `read` tool, not `Get-Content` (ANSI default misleads).
- [2026-10-20, M7A] A fixed-position modal rendered inside `.portal-main` was clipped to the content column (`x=398` instead of centred) and did not dim the sidebar, because the page entry animation sets a transform and becomes the containing block for `position: fixed`. Fix: render `Modal` through `createPortal(..., document.body)`.
- [2026-10-20, M7A] Headless Chromium does not render PDFs inside an `<iframe>` (blank white area), although headed Chromium shows the built-in viewer normally. Use a headed browser for PDF-preview screenshots; do not treat the blank headless iframe as a UI bug.
- [2026-10-20, M7A] UI screenshots taken before the page entry animation settles look washed out (opacity < 1). Wait 800-1200 ms after navigation or after a route change before `page.screenshot()`.

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
- [2026-10-19, M4] The Candidate Service accepts recruiter tokens with ONE authentication class (`IssuerAwareJWTAuthentication`) that reads the unverified `iss` and selects the verifying key (own signing key for candidate tokens, `JOB_SERVICE_JWT_PUBLIC_KEY` for job-service tokens). Why: one auth path for both audiences; the peer public key comes from env. Rejected: a second authentication class per route (route-level duplication), custom middleware (same effect, more moving parts).
- [2026-10-19, M4] The consumer publishes its state through a singleton `consumer_status` heartbeat row that `/readyz` reads (fresh <= 15 s, else `stale`). Why: the consumer is a separate process, so the web process can only learn its state through the DB. Rejected: running the consumer inside the web process (double consumer-group membership), a file or Redis heartbeat (extra dependency).
- [2026-10-19, M7 (dev only, human-approved)] Added a one-command dev stack (`deploy/docker-compose.dev-full.yml` + `backend/Dockerfile.dev` + `tasks.ps1 stack-up`) so `docker compose up -d --build` starts kafka, both DBs, both services, the relay and the consumer. Why: the human asked for one command instead of four terminals; it does not conflict with M7, which still owns the PROD images (gunicorn, non-root, multi-stage), Caddy, the health-gated migration flow and the CI. The dev image is deliberately separate from the prod Dockerfile and uses bind mounts for hot reload.
- [2026-10-19, M5] Search SQL is duplicated per service (`apps/jobs/search.py`) rather than shared in `packages/contracts`. Why: invariant I1 forbids importing the other service's code and `contracts` must stay schema-only; each service owns its database and its own `cjobs_*` index names. Rejected: a shared search library (would make `contracts` a runtime dependency with DB access).
- [2026-10-20, M6] The snapshot endpoint takes `after` (keyset by id) plus an optional `updatedAfter` and returns `{items, nextAfter, hasMore}`; `limit` is capped at 1000 (default 500). Why: keyset paging keeps full-mode passes linear at 100k rows, and the incremental window needs a time filter without a second endpoint.
- [2026-10-20, M6] `InternalJobDetailView` (`GET /internal/jobs/<uuid>`) was added in M6 and closes the M4 P1 sync-fallback item. Why: the reconciler needs one row by id on demand; the same route serves a future fallback with no extra code.
- [2026-10-20, M6] The reconciler never deletes local rows. Full-mode "local row absent from source" is detected with a temp-table diff and logged as an anomaly. Why: a source bug or a partial page must not destroy replica data; convergence only ever adds or upgrades rows.
- [2026-10-20, M6] Reconciliation runs in a management command (`run_reconciler`), not in the web process, and the e2e runner stops that container when it wants a deterministic reconcile. Why: a background full pass could repair the damage in the middle of a scenario and hide a defect.
- [2026-10-20, M6] DLQ replay has ONE implementation (`apps/events/dlq.py`), exposed both as an HTTP admin endpoint and a management command; `scripts/replay_dlq.py` only calls the endpoint. Why: two Kafka clients in two languages would drift. Replay reads at most the DLQ size at call start, so an unfixable message cannot loop.
- [2026-10-20, M7] Frontend visual pass (pre-M7, human-requested): kept the existing design world (petrol ink, warm paper, amber = Job API, teal = Candidate) and refined it instead of replacing it. Wordmark is Devanagari (`जागीर`) plus a small Latin line; the signal path (Job API -> Kafka -> Candidate) is the single authored motion moment; kickers/eyebrows and colored left bars were removed per the craft-floor rules. Why: the human asked for "good, not over the top". Rejected: a full redesign (the world was already distinctive), new UI dependencies (none added).
- [2026-10-20, M7] The frontend container is a multi-stage build (`node:22-slim` -> `nginxinc/nginx-unprivileged`) because production needs only static files; Caddy still terminates TLS in front of it. Why: small runtime image, no Node process in production, non-root by default. Rejected: `vite preview` in the container (dev server in prod), a Node server process (extra surface, more RAM).
- [2026-10-20, M7] Added a root `docker-compose.yml` that only sets the project name and includes `deploy/docker-compose.dev-full.yml`, so the default commands `docker compose build` and `docker compose up -d` (run from the repo root) start the whole stack, frontend included. Why: the human wants zero host processes and no `npm run dev`. Rejected: duplicating all service definitions at the root (two sources of truth), telling the user to pass `-f` (easy to forget, and a wrong `-f` changes the project name and the volumes).
- [2026-10-20, M7] Two visual worlds in one SPA: the public site uses a warm paper theme, plain language, larger type, and soft motion; `/admin` keeps the dark technical console and may use jargon (Kafka, outbox, DLQ, JSON). Why: human direction; recruiters and candidates must not read infrastructure terms, while operators need them. Routing is path-based (`/`, `/jobs`, `/employers`, `/me`, `/admin`) so links are shareable and nginx SPA fallback serves every page.
- [2026-10-20, M7] Admin authentication is `POST /internal/admin/login` with `{username, password}` compared against `ADMIN_USERNAME`/`ADMIN_PASSWORD` from each service `.env`; it returns that service's `INTERNAL_TOKEN` as `{service, token}`. The console signs in to both services at once and keeps the tokens in `localStorage`. Why: operators should not paste raw internal tokens; credentials stay out of git (I6). Rejected: a separate admin user table (no need for one account), reusing recruiter JWTs (wrong audience, no ops permissions).
- [2026-10-20, M7] The whole portal (public site and `/admin`) is served by the frontend nginx container on **5174**; there is no separate admin port and no host Vite process. Why: human direction ("the whole portal runs on 5174"). Rejected: a second container/port for admin (unnecessary), dev server on 5173 (requires host Node).
- [2026-10-20, M7] Job search runs live with a 350 ms debounce; the result count and the rows come from the same response, and the `q`/filter values are mirrored into the URL with `replaceState` (shareable links, no extra history entries). Why: the human reported a count that did not match the rows and asked for real-time search or an honest label. Rejected: keeping click-only search (slower), updating the label before the response (the original bug).
- [2026-10-20, M7] Role detail sits beside the results in a sticky column above 980 px and scrolls into view on selection below it. Why: "View role" forced a long scroll past the list and pager. Rejected: a modal (hides context, extra focus handling).
- [2026-10-20, M7] The account pages name their audience in the heading: "Job seeker sign in" at `/me`, "Employer sign in" at `/employers`, plus a cross-link ("Hiring instead?" / browse roles). Why: the human could not tell which account `/me` was for. Rejected: an eyebrow label above the heading (violates the public craft-floor rules).
- [2026-10-20, M7A] CV upload is in scope despite ARCHITECTURE §13 ("no file uploads"): PDF only, max 5 MB, stored on the Candidate Service volume, served only through guarded endpoints. Why: explicit human request ("allow uploading cv pdfs"); a URL-only resume does not let recruiters inspect the CV. Rejected: DOCX (parsing risk), S3 (new infrastructure before M7/M8), public media URLs (leaks resumes). Consequence: §13 and the M7/M8 storage/backup tasks are updated.
- [2026-10-20, M7A] Sessions use access 1 h + refresh 7 days in both services. Why: human wants reload and return visits to stay signed in, and the existing access-only token expires after an hour with no recovery. Rejected: longer access tokens (revocation impossible), cookie sessions (cross-origin frontend/API setup).
- [2026-10-20, M7A] The SPA uses `react-router-dom` instead of the hand-written path switch. Why: nested layouts, URL params (`/employers/roles/:id`), guards and `?next=` redirects are first-class; the old switch cannot express them cleanly. Rejected: extending the custom router (more bespoke code, no params/history helpers).
- [2026-10-20, M7A] One active identity per browser: signing in as a recruiter clears the candidate session and the reverse also holds. Why: prevents two contradictory dashboards and wrong-role API calls; matches the human's "logged in session be it a recruiter or a job seeker". Rejected: keeping both sessions with a role switch (ambiguous root redirect, confusing header).
- [2026-10-20, M7A] A recruiter may read a candidate's name, email, phone, headline, skills, summary and CV **only** through applications to that recruiter's jobs. Why: hiring needs contact data, but the candidate profile must not become a public directory (I1/privacy). Enforced in the Candidate Service by `job.recruiter_id == token.sub`; foreign applications return 404.
- [2026-10-20, M7A] `/jobs/:id` is a real, shareable job page; the side-by-side detail panel is retired. Why: LinkedIn-style multipage flow and deep links from applications/CVs need a stable URL; the sticky panel cannot be linked or refreshed. The search list keeps live debounce and applied-filter labels.
- [2026-10-20, M7A] Recruiter status changes are `PATCH /recruiter/applications/:id/status` with the four post-submission statuses; `SUBMITTED` stays the apply default. Why: applicant tracking is the point of the recruiter portal; ownership and allowed values are validated server-side, `status_updated_at` is bumped.
- [2026-10-20, M7A] Portal routes are a flat list under pathless layout routes (`RequireRole` + `PortalShell`), not nested splats. Why: React Router v7 ranks `employers/*` above the exact `/employers` sign-in route, which produced an infinite `?next=` loop. Rejected: nested splat layouts (correct-looking, but cannot host the same-prefix public sign-in page).
- [2026-10-20, M7A] Sign out does a full reload (`window.location.replace("/")`) instead of a soft `navigate`. Why: the guard re-renders before the state update and sends the user back to the sign-in page. Rejected: `flushSync` or a delayed navigate (both brittle).
- [2026-10-20, M7A] The e2e stack publishes the built frontend on `:15174` and points its build args at `:13001`/`:13002`. Why: the dev stack owns `:5174`, and the e2e run must not fail on a port clash before any reliability scenario starts.

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

### Session 6: 2026-10-19: M4 (Candidate Service core + consumer) — M4 COMPLETE
- Did: implemented the whole Candidate Service: models + migrations (`candidates`, `jobs` replica, `applications` with `UNIQUE (candidate_id, job_id)`, `processed_events`, `consumer_status`), candidate auth (`apps/candidates` + `apps/core/authentication.py` `IssuerAwareJWTAuthentication`), the version-guarded replica upsert (`apps/jobs/repo.py` `UPSERT_JOB_SQL`, `apps/jobs/services.py` `upsert_job_from_snapshot`), the consumer (`apps/events/services.py` `apply_envelope` = inbox insert + upsert in ONE tx; `apps/events/consumer.py`; `management/commands/consume_events.py`), applications (`apps/applications/*`: apply with 409 `APPLICATION_ALREADY_EXISTS` via SQLSTATE 23505, history, recruiter view with ownership), `/readyz` consumer state via the `consumer_status` heartbeat, and tests (`test_consumer.py` 7, `test_applications.py` 6, `test_auth.py` 6, `test_health.py` 6).
- Verified (commands + result):
  - `./tasks.ps1 verify` -> ruff "All checks passed", format "125 files already formatted", mypy "Success" x3, pytest 11 + 49 + 27 = 87 passed.
  - Live end-to-end (all four processes up): recruiter register/login on :3001 -> create DRAFT v1 -> publish v2; candidate replica `GET /jobs/:id` 200 with `version: 2`, `PUBLISHED` within ~1 s; candidate register (token `role=candidate`, `iss=candidate-service`) -> apply 201 with title/company snapshots -> duplicate 409 `APPLICATION_ALREADY_EXISTS` -> history `total: 1`; recruiter A `GET /recruiter/jobs/:id/applications` `total: 1` (Job-Service token accepted cross-service) -> recruiter B 404 `JOB_NOT_FOUND`; close -> replica `CLOSED version 3` -> apply 409 `JOB_NOT_OPEN`; DB check `processed_events: 7`, `applications: 1`.
  - Consumer live: on boot it replayed the M3 backlog `fromBeginning` and applied each event once (`event applied` x6, no duplicates); `GET /readyz` with Kafka up -> `{"consumer":"up","kafka":"up"}`; with Kafka down -> `GET /healthz` 200 and `/readyz` `status: "ok"` (invariant I9).
  - One-command dev stack live (`docker compose -f deploy/docker-compose.dev-full.yml up -d --build`): 9 services up, both migrations exit 0, both `/readyz` healthy (`candidate` reports `consumer: up`, `kafka: up`), a published job reached the candidate replica in ~2 s, outbox `{pending:0, publishedLastHour:1}`.
- Not done / left half-way: M4 P1 items (recruiter `PATCH /recruiter/applications/:id/status`, sync fallback `GET /internal/jobs/:id`). The live Kafka-stop/start cycle for the consumer was **not** re-run at the end (M6 owns the formal outage proof); the I9 availability half (healthz 200 with Kafka down) was observed. M6 not started.
- Gotchas/decisions added: build/type issues (`headers()` union type -> `cast`, SimpleJWT needs `jti`, empty verifying key breaks ES256 -> peek `iss` with PyJWT); operational (`--noreload` serves stale readyz code -> restart the listener; unbounded poll loops blow the tool timeout -> use `curl.exe -m 2` with few iterations); candidate dev `.env` needs its own ES256 keypair + the Job Service public key. Decisions: `IssuerAwareJWTAuthentication` selects the key from `iss`; consumer state via a DB heartbeat row.
- Next session should start with: M5 Search — trigger + `search_vector` + GIN indexes in BOTH services, the query module (`websearch_to_tsquery`, weighted `ts_rank_cd`, filters, `page/pageSize`, `total`), `GET /jobs` on both services, `scripts/seed_jobs.py` (`make seed N=100000`), `scripts/explain_analyze.sh`, `docs/search-performance.md`.

### Session 7: 2026-10-19: M5 (search) — M5 COMPLETE
- Did: search in BOTH services. Migrations `apps/jobs/migrations/0002_job_search.py` (trigger `jobs_search_vector_trg`, weights A/B/C, backfill via `SET search_vector = NULL`, partial GIN on PUBLISHED, GIN on skills, browse/employment/lower(location) btrees; candidate uses `cjobs_*` names). Query modules `apps/jobs/search.py` in both services (`websearch_to_tsquery`, `ts_rank_cd`, fixed filter fragments with bound params, `LIMIT/OFFSET`, separate `COUNT`, `NULLS LAST` tie-break). Endpoints `GET /jobs` on :3001 (`PublicJobSearchView`) and :3002 (`JobSearchView`) with `JobSearchParamsSerializer` (`q`, `employmentType`, `location`, `skills`, `page`, `pageSize` max 50). Scripts `scripts/seed_jobs.py` and `scripts/explain_analyze.py`; `tasks.ps1 seed -N` / `explain` and `make seed` / `explain` wired. `docs/search-performance.md` written from real plans. Tests `job-service/tests/test_search.py` (20) and `candidate-service/tests/test_search.py` (15).
- Verified (commands + result):
  - `./tasks.ps1 verify` -> ruff "All checks passed", format "129 files already formatted", mypy "Success" x3, pytest 11 + 69 + 42 = 122 passed.
  - Migration live on both DBs: `search_vector` = `'acm':6B 'build':7C 'django':8C 'engin':3A 'kafka':2A,4B 'python':5B 'senior':1A`; trigger `jobs_search_vector_trg` present; all 9 indexes present.
  - Seeded 100,207 rows (job) and 100,205 rows (candidate) in ~21 s each; `ANALYZE jobs` run.
  - `scripts/explain_analyze.py` at 100k: Job Q1 173.256 -> 29.097 ms, Q2 88.122 -> 16.311 ms, Q3 84.783 -> 3.136 ms; Candidate Q1 60.519 -> 24.136 ms, Q2 76.225 -> 18.576 ms, Q3 91.586 -> 2.598 ms. Indexed plans show `Bitmap Index Scan on jobs_search_vector_gin` / `cjobs_search_vector_gin` / `jobs_skills_gin`.
  - Live through the dev stack: `GET :3001/jobs?q=python%20engineer` -> `total: 3707`; `GET :3002/jobs?q=kubernetes&employmentType=CONTRACT` -> `total: 1584`; hostile `q` -> 200; bad `employmentType` -> 400.
- Not done / left half-way: M5 has no P1 items. The dev stack is running with 100k seeded rows in both databases (do not re-seed blindly: `--count` is additive).
- Gotchas/decisions added: `SET LOCAL` no-op outside a transaction -> session `SET` + `RESET`; psycopg3 has no `copy_expert` -> `cursor.copy()`; `auto_now` columns have no DB default so raw COPY must supply them; per-service column intersection via `information_schema`; `NULLS LAST` required for browse; Seq Scan at small row counts is correct; search SQL duplicated per service (I1).
- Next session should start with: M6 — Job Service `GET /internal/jobs/snapshot?after&limit` (keyset, non-DRAFT, full payloads, token-guarded), the Candidate reconciler (full + incremental, `reconcile_runs`, `POST /internal/admin/reconcile`, `GET /internal/admin/sync-status`) reusing `upsert_job_from_snapshot`, `scripts/replay_dlq.py` + `POST /internal/admin/dlq/replay`, the `e2e/` scenarios A-E, and `docs/outage-recovery.md` with real transcripts.

### Session 8: 2026-10-20: M6 (reconciliation + DLQ + outage proof) — M6 COMPLETE
- Did: Job Service snapshot API (`apps/jobs/snapshot.py::to_snapshot`, `apps/jobs/internal_views.py`: `GET /internal/jobs/snapshot`, `GET /internal/jobs/<uuid>`; outbox now reuses `to_snapshot`), tests `test_internal_snapshot.py` (11). Candidate reconciler (`apps/events/reconciler.py`, `job_client.py`, `ReconcileRun` model + `events.0003_reconcilerun`, `POST /internal/admin/reconcile`, `GET /internal/admin/sync-status`, `management/commands/run_reconciler.py`, `RECONCILE_*` settings), tests `test_reconciler.py` (12). DLQ replay (`apps/events/dlq.py`, `POST /internal/admin/dlq/replay`, `management/commands/replay_dlq.py`, `scripts/replay_dlq.py` HTTP client), tests `test_dlq.py` (3). Compose parameterized (`COMPOSE_PROJECT_NAME`, `*_PORT`) and a `candidate-reconciler` service added to the dev-full stack. `e2e/run_e2e.py` with scenarios A-E + `scripts/demo_kafka_outage.sh`, wired to `make e2e` / `tasks.ps1 e2e`. `docs/outage-recovery.md` written with real transcripts.
- Verified (commands + result):
  - `./tasks.ps1 verify` -> ruff "All checks passed", format "141 files already formatted", mypy Success x3 (5/70/83 files), pytest 11 + 80 + 57 = 148 passed.
  - `uv run --project backend python e2e/run_e2e.py` -> `5/5 scenarios passed in 110.3s` (A 7.5 s, B 12.6 s, C 12.5 s, D 13.4 s, E 15.6 s); two more consecutive full runs `110.3s` and `101.8s`; a fourth run after BOM/format cleanup `240.5s` (host under load). Final assertion each run: "8 non-draft jobs identical in both databases".
  - Scenario D numbers: DLQ `read=2 published=0` (dry run) then `read=2 published=2`; scenario C `checked=4 repaired=1`; scenario E rebuilt 1 row with no events available.
  - `python scripts/replay_dlq.py --help` -> usage OK (thin HTTP client; endpoint is the only implementation).
- Not done / left half-way: nothing half-written. `scripts/demo_kafka_outage.sh` was not executed on this box (no bash; it only narrates and calls the same runner). M4 P1 `PATCH /recruiter/applications/:id/status` still open (non-P1 work for later).
- Gotchas/decisions added: partial PUT body rejected (send full snapshot); `executemany` needs tuples; temp table (`PRESERVE ROWS` + explicit `DROP`) for the 100k-id diff; `docker exec` Kafka helpers hang on Windows -> use `confluent-kafka` from the host; replay feedback loop -> bound read set to the DLQ watermark snapshot; PowerShell BOM breaks ruff/mypy (`pyproject.toml` too); e2e `base=` routing; scenario A must restore Kafka in `finally`. Decisions: snapshot `after`+`updatedAfter`+`limit<=1000`; internal detail route closes the M4 P1 fallback; reconciler never deletes; reconcile runs as a management command; single DLQ replay implementation.
- Next session should start with: M7 — prod Dockerfiles (multi-stage, repo-root context, non-root, healthcheck), `deploy/docker-compose.prod.yml`, `deploy/Caddyfile`, `deploy/scripts/{bootstrap-vps,render-env,deploy,rollback,backup-db}.sh`, the full `ci.yml` (integration + migration check + image build + actionlint + e2e on main + secret scan + lockfile freshness) and `deploy.yml`, then `docs/deployment.md`.

### Session 9: 2026-10-20: Frontend design pass + frontend container (pre-M7)
- Did: full frontend quality pass (human-requested, "good, not over the top"). Rewrote `frontend/src/styles.css` with a token system, themed browser surfaces (selection, scrollbars, caret, focus ring), a 120-180 ms motion budget (`--ease-out: cubic-bezier(0.23,1,0.32,1)`), skeletons, and responsive rules at 1024/640 px. `App.tsx` now has the Devanagari wordmark (`जागीर`), a `SignalPath` component (Job API -> Kafka -> Candidate, driven by the `/readyz` checks) as the single authored motion moment, a readiness badge row, and hash routing (`#discover`/`#recruiter`/`#candidate`/`#ops`). `ui.tsx` `Panel` header lost the eyebrow/kicker and now shows the service badge inline; added `Skeleton`. Discover got loading skeletons and left-aligned submit; Ops probes show each base URL as `.probe` blocks. Then containerized the frontend: `frontend/Dockerfile` (multi-stage `node:22-slim` -> `nginxinc/nginx-unprivileged:1.27-alpine`, uid 101, port 8080, `/healthz`, `HEALTHCHECK`), `frontend/nginx.conf` (SPA fallback, immutable asset cache, security headers), `frontend/.dockerignore`, and a `frontend` service on `:5174` in `deploy/docker-compose.dev-full.yml` that waits for both web healthchecks.
- Verified (commands + result):
  - `npm run build` -> clean (`tsc -b` + Vite, 37 modules; `dist/assets/index-*.js` ~273 kB, gzip ~81 kB).
  - `.opencode/skills/impeccable/scripts/impeccable.cmd detect --json frontend/src` -> `[]` (no craft-floor violations in the detector's ruleset).
  - Headless Edge screenshots at 1440 px (Discover, Recruiter, Candidate, Ops) and 500 px (Discover, Ops): no horizontal overflow, no clipped controls, signal path readable.
  - `./tasks.ps1 verify` -> ruff clean, format 141 files, mypy Success x3, pytest 11 + 80 + 57 = 148 passed (backend untouched).
  - Root `docker-compose.yml` (project name pinned to `jobportal-dev`, includes dev-full) -> plain `docker compose build` then `docker compose up -d` starts all 11 services; `docker compose config` -> name `jobportal-dev`; :5174 -> 200, :3001/readyz -> 200, :3002/readyz -> 200 with consumer `up` and kafka `up`; seeded jobs still present (no new volumes).
  - `docker compose -f deploy/docker-compose.dev-full.yml up -d --build frontend` -> container `(healthy)`; `GET :5174/healthz` -> 200 `ok`; `/` and `/ops` -> 200; screenshot of `:5174` shows the same design with live 100k-row search results (180,559 hits, 10 ms).
- Not done / left half-way: no true 390 px check (headless Edge clamps the viewport to ~486 px; see Gotchas). No bundled Devanagari font yet, so the wordmark uses Nirmala UI on this box and another font on macOS/Linux. M7 prod compose/Caddy/deploy scripts/CI still open.
- Gotchas/decisions added: Edge viewport clamp; PowerShell non-ASCII/BOM handling; write-tool BOM retention; `workdir`-relative .NET paths; Nirmala-only Devanagari rendering; nginx-unprivileged port 8080 + BusyBox wget; Vite build-time env. Decisions: refine (not replace) the design world; signal path as the only authored motion; static nginx image behind Caddy.
- Next session should start with: M7 prod Dockerfiles for both Django services, `deploy/docker-compose.prod.yml`, `deploy/Caddyfile` (two domains, `/internal/*` -> 404), `deploy/scripts/*`, full `ci.yml` + `deploy.yml`, `docs/deployment.md`. Optional frontend follow-up: bundle a subsetted Devanagari font and serve same-origin API paths behind Caddy (removes CORS from prod).

### Session 10: 2026-10-20: Two-world frontend + admin login (pre-M7)
- Did: split the SPA into a public site and a technical admin console. Added path routing in `App.tsx` (`/`, `/jobs`, `/employers`, `/me`, `/admin`), a public shell (wordmark, nav, account pill, footer) and `body[data-world]` theming. New `views/Landing.tsx` (hero with live open-role count, "I am looking for work" / "I am hiring", three steps). New `public.css` warm paper theme with larger type, glow drift, card float, hover lift, and reduced-motion guards; `views/Ops.tsx` moved behind `views/Admin.tsx` (dark) and now takes `jobToken`/`candidateToken` instead of a pasted internal token. Rewrote `Discover`, `Recruiter`, `Candidate` copy and layout for plain language (no service names, ids, versions, JSON, replica/throttle talk); engineer-facing detail stays only in `/admin`. Backend: `POST /internal/admin/login` in both services (`apps/core/admin_views.py`) comparing `ADMIN_USERNAME`/`ADMIN_PASSWORD` (constant-time) and returning `{service, token}` = `INTERNAL_TOKEN`; new `ADMIN_*` settings/env; tests 5 + 3. Fixed the real `AuthRateThrottle` bug (see Gotchas). Changed the frontend container to publish **5174** (whole portal); removed the stale host Vite process. Root compose/README updated.
- Verified (commands + result):
  - `npm run build` -> clean (41 modules; 279.8 kB JS / 34.9 kB CSS).
  - `docker compose build frontend` + `up -d frontend` -> healthy; `/healthz` 200; `/`, `/jobs`, `/employers`, `/me`, `/admin` -> 200 on `:5174`.
  - `POST :3001/internal/admin/login` and `:3002/internal/admin/login` with the dev credentials -> `{"service":"job","token":"..."}` / `{"service":"candidate","token":"..."}`.
  - Live `:5174/jobs` -> 209,168 roles with live results; headings, filters, cards, footers readable at 1440 px and 500 px (screenshots).
  - `./tasks.ps1 verify` -> ruff clean, format 145 files, mypy Success x3, pytest 11 + 85 + 60 = 156.
- Not done / left half-way: no true 390 px check (Edge clamps to ~486). Admin dashboard body (after sign-in) was type-checked and the login screen screenshotted, but not exercised in a real browser session; manual step: sign in at `/admin` with `admin` / the `.env` password and confirm outbox/sync/DLQ panels load. M7 prod compose/Caddy/deploy scripts/CI still open.
- Gotchas/decisions added: throttle scope bug; screenshot animation timing (`--virtual-time-budget`); two `.env` admin passwords must match; stale Vite on 5173. Decisions: two visual worlds; env-based admin login returning the internal token; one container/port (5174) for everything.
- Next session should start with: M7 prod Dockerfiles for both Django services, `deploy/docker-compose.prod.yml`, `deploy/Caddyfile`, `deploy/scripts/*`, full `ci.yml` + `deploy.yml`, `docs/deployment.md`.

### Session 11: 2026-10-20: Frontend fixes + README screenshots (pre-M7)
- Did: fixed the three issues the human reported on the public site. (1) `/me` now says "Job seeker sign in" / "Create a job seeker account" and cross-links to the employer sign in; `/employers` says "Employer sign in" (headings name the audience; no eyebrow labels). (2) Job search is live: 350 ms debounce, `applied` filters drive the label and pager, a request sequence guard drops stale responses, the URL mirrors the filters with `replaceState`, and "Clear filters" only appears when a filter is active. `Discover.tsx` was reorganised into a results list plus a sticky detail column. (3) Role detail sits beside the list at >= 981 px and scrolls into view on narrow screens; added a Close button. Added `docs/screenshots/{landing,jobs,search-python,job-seeker,employers,admin}.png` (1440x1000, headless Edge, sign-in screens only) and a Screenshots section to `README.md`. Updated `.env.example` CORS examples from 5173 to 5174.
- Verified (commands + result):
  - `npm run build` -> clean (41 modules, 281.96 kB JS / 35.68 kB CSS).
  - `docker compose build frontend && docker compose up -d frontend` -> healthy; :5174 serves the new bundle (`index-BN9Ou5uG.js`).
  - Live deep link `:5174/jobs?q=python` -> label `18,806 roles for "python"` with matching rows (screenshot); browse shows `209,168 roles` with no query label.
  - `/me` DOM contains "Job seeker sign in" and "Go to the employer sign in"; `/employers` screenshot shows "Employer sign in".
  - `./tasks.ps1 verify` -> ruff clean, 145 files formatted, mypy Success x3, pytest 11 + 85 + 60 = 156.
  - README screenshots render from repo-relative paths (`docs/screenshots/*.png`).
- Not done / left half-way: none in this slice. Admin dashboard after sign-in still not exercised in a real browser session. M7 prod images/compose/Caddy/scripts/CI still open.
- Gotchas/decisions added: applied-filters label bug + sequence guard; sticky detail vs long scroll; unique `--user-data-dir` per headless capture. Decisions: live debounced search with URL sync; side-by-side detail; audience-named headings.
- Next session should start with: M7 prod Dockerfiles for both Django services, `deploy/docker-compose.prod.yml`, `deploy/Caddyfile`, `deploy/scripts/*`, full `ci.yml` + `deploy.yml`, `docs/deployment.md`.

### Session 12: 2026-10-20: M7A planning (no code)
- Did: turned the human's portal feedback into the M7A milestone above (multipage recruiter/candidate flows, applicant profiles, CV upload/preview, refresh-token sessions, applicant status). Recorded the human decisions (PDF <= 5 MiB, refresh 7 days, `react-router-dom`, one active role, 404 privacy for foreign applicants) in the Decisions log. Updated ARCHITECTURE.md §4.2, §8, §9, §10, §11, §13 for the CV exception/media volume and the new endpoints. No production code changed.
- Verified (commands + result): no code run; `git status` shows only docs changes from this planning step (plus the uncommitted S11 frontend work).
- Not done / left half-way: implementation starts with the candidate resume model/migration and the guarded upload/download endpoints. M7 infra remains paused until M7A passes.
- Gotchas/decisions added: decisions M7A x8 (CV exception, refresh sessions, router, single identity, applicant privacy, `/jobs/:id`, recruiter status change).
- Next session should start with: M7A backend. Read this milestone, then add `resume_file`/`resume_filename`/`resume_uploaded_at` + migration, the multipart upload/delete/download endpoints with PDF magic + 5 MiB checks and tests, then dashboards + applicant detail/status + refresh tokens. Do not start the frontend rewrite before those endpoints return real data.

### Session 13: 2026-10-20: M7A Phase 1 (backend)
- Did: resume storage (`apps/candidates/models.py` random `resumes/<uuid>.pdf`, `resume_filename`, `resume_uploaded_at`; migration `candidates.0002_resume_file`), env/settings (`MEDIA_ROOT`, `RESUME_MAX_BYTES`), guarded `apps/candidates/resume.py` (PDF magic, size, delete-on-replace/remove, `FileResponse` + `nosniff` + `attachment`), candidate resume routes, recruiter applicant list/detail/status/resume routes, candidate and recruiter dashboards, per-role applicant counts, refresh tokens in both services (1 h access / 7 days refresh) and auth responses carrying `refresh`/`refreshExpiresIn`. Fixed OpenAPI validation (operation ids, enum overrides, auth extension, internal POST `request=None`).
- Verified (commands + result):
  - `./tasks.ps1 verify` -> ruff clean, format 150 files, mypy Success x3, pytest 11 + 89 + 78 = 178.
  - `./tasks.ps1 migrate` -> `candidates.0002_resume_file` applied to `candidate_db` (job DB no migrations).
  - `manage.py spectacular --validate --fail-on-warn` -> exit 0 for both services.
  - Live smoke on :3002: register -> upload 200 `has_resume=true` -> download 200 `%PDF-` with `application/pdf`, `attachment`, `nosniff` -> refresh 200.
- Not done / left half-way: Phase 2 frontend foundation (router, session, shells, guards, `/jobs/:id`) and Phase 3 portal pages; screenshots, container rebuild, manual walkthrough, e2e. No commit made.
- Gotchas/decisions added: OpenAPI warning set + fixes; empty `FileField` needs `allow_empty_file=True`; `FileResponse` open handle vs `SIM115`.
- Next session should start with: Phase 2. Add `react-router-dom`, `lib/session.tsx` (access+refresh, single-flight refresh on 401, storage sync, sign-out, `?next=`), `PublicShell`/`PortalShell`, route guards, signed-in redirects, and make `/jobs/:id` a real page. Do not touch `/admin`.
### Session 14: 2026-10-20: M7A phases 2-3 (frontend) — M7A COMPLETE
- Did: rewrote the SPA around `react-router-dom`: `App.tsx` route tree (pathless `RequireRole` + `PortalShell` layouts with explicit child paths), `layouts/{PublicShell,PortalShell}.tsx`, `lib/{session,api,types,useAsync,files,format}.ts(x)`, `views/public/{Jobs,JobDetail,RecruiterSignIn,CandidateSignIn}.tsx`, 12 `views/portal/*` pages (recruiter dashboard/roles/role/role-edit/applicants/applicant/profile/post; candidate dashboard/applications/application/profile), `portal.css` (~500 lines) and a README "Signed-in portals" section. Removed the pre-router `Discover.tsx`/`Recruiter.tsx`/`Candidate.tsx`.
- Verified (commands + result):
  - `npm run build` -> clean (73 modules, 349.8 kB JS / 46.6 kB CSS); `docker compose build frontend` + `up -d frontend` -> healthy on `:5174`.
  - Playwright walkthrough (bundled chromium) -> Publish -> search -> apply -> CV upload/download (`%PDF-`) -> applicant detail -> status `SHORTLISTED` visible to the candidate -> silent refresh -> reload persistence -> signed-out redirects -> sign-out -> 500 px no overflow.
  - 16 portal screenshots at 1440 + 500 px in `docs/screenshots/`; inspected after a header-height fix.
  - `./tasks.ps1 verify` -> ruff clean, format 150 files, mypy Success x3, pytest 11 + 89 + 78 = 178.
  - `./tasks.ps1 e2e` -> `5/5 scenarios passed in 207.0s` (A 20.0, B 24.6, C 18.7, D 20.9, E 36.0); final assertion `8 non-draft jobs identical in both databases`.
- Not done / left half-way: no commit made. `case`/`snake` nuance none. M7 (prod Dockerfiles, prod compose, Caddy, deploy scripts, full CI) not started.
- Gotchas/decisions added: React Router splat ordering loop; full-reload sign-out; stretched single-column grid header (266 px -> 98 px); Playwright Edge channel hangs -> bundled chromium; e2e frontend port `:15174`; one transient Docker Desktop 500 during e2e (rerun green); CONTEXT mojibake repaired with `ftfy`.
- Next session should start with: M7 — prod Dockerfiles for both Django services (repo-root context, non-root, healthcheck), `deploy/docker-compose.prod.yml`, `deploy/Caddyfile`, `deploy/scripts/*`, full `ci.yml` + `deploy.yml`, `docs/deployment.md`.
### Session 15: 2026-10-20: M7A CV upload polish (follow-up)
- Did: removed the "profile strength" percentage card from the candidate dashboard. Added a dismissible, inline CV reminder that shows only when no CV is uploaded (`jp.cvReminder` in localStorage); it is a normal card, not a popup. Rebuilt the CV panel: dashed drop zone with drag and drop, hidden file input behind a "Choose file" button, explicit Upload/Replace button, file card with Preview/Download/Remove, and a PDF preview modal (`createPortal`, ESC/backdrop close, Download + Close actions, blob URL revoked on close). Profile copy changes for first upload vs replace. README screenshots keep the landing page and now show the core flows instead of the sign-in pages.
- Verified (commands + result):
  - `npm run build` -> clean (73 modules, 351.75 kB JS / 50.07 kB CSS); `docker compose build frontend` + `up -d frontend` -> healthy on `:5174`.
  - Playwright (bundled chromium) on a fresh candidate: reminder visible -> dismissed -> stayed hidden after reload; upload `mira-cv.pdf` -> file card; Preview -> modal with `blob:` iframe; Download -> `mira-cv.pdf`; reminder gone after upload; 0 px overflow at 500 px for profile and modal.
  - Headed Chromium confirmed the PDF renders inside the modal at 1440 and 500 px (headless shows a blank iframe, see Gotchas).
  - New screenshots: `cv-reminder-1440/500`, `cv-upload-empty-1440`, `cv-upload-ready-1440`, `candidate-profile-cv-1440/500`, `cv-preview-modal-1440/500`.
- Not done / left half-way: no commit. No automated frontend test suite (manual Playwright only). M7 still next.
- Gotchas/decisions added: modal portal for transformed ancestors; headless Chromium PDF iframe; screenshot timing vs page animation.
- Next session should start with: M7 production Dockerfiles/compose/Caddy/CI.