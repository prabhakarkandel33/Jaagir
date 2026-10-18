# AGENTS.md

You are a coding agent building the **Job Portal** (two Kafka-connected microservices on PostgreSQL). Source of truth for requirements: `docs/ASSIGNMENT.md`. This file is auto-loaded by opencode every session. Follow it exactly.

## 0. Read order (every session, no exceptions)

1. This file.
2. `CONTEXT.md`: status board, milestones, gotchas, session log. **This tells you what to work on.**
3. `ARCHITECTURE.md`: only the sections relevant to your milestone (the section index is at the top).

Do not start coding before you have done all three and stated your plan in 3-6 lines.

## 1. Session protocol

**START**
1. `git status && git log --oneline -10`. Understand where the last session stopped.
2. Run `make verify` to learn the baseline. If it is red before you touch anything, fix that first (or record why in CONTEXT.md).
3. Find the **current milestone** in `CONTEXT.md` > Status board. Work on that milestone only.

**DURING**
- Work through the milestone checklist in order. Small commits (Conventional Commits: `feat(job): ...`, `fix(candidate): ...`, `chore(context): ...`).
- Write the test first for anything in the reliability path (outbox, consumer, reconciliation, DLQ).
- The moment you hit something surprising (a library quirk, a version issue, a decision you had to make), append it to `CONTEXT.md` > Gotchas **right then**. Do not wait for the end of the session; you may run out of context.
- Do not do work from a later milestone. If you notice something needed later, add it as a bullet under that milestone in `CONTEXT.md`.
- Stuck for more than ~3 attempts on the same error: stop, write what you tried in Gotchas, pick the simplest alternative that still satisfies the invariants, record it in the Decisions log. If it needs a human (credentials, DNS, VPS, approval), write it under "Blocked / needs human" and move to the next unblocked task.

**END (mandatory, even if the session is cut short)**
1. Run `make verify` (and the milestone's acceptance commands).
2. Tick checklist boxes in `CONTEXT.md` **only for items whose acceptance command you actually ran and saw pass**. Never tick on belief.
3. Update the Status board (current milestone, state, next action).
4. Append new Gotchas and Decisions (dated, one or two lines each, include the *why* and the fix).
5. Append a Session log entry using the template at the bottom of `CONTEXT.md`.
6. Commit: `chore(context): end of session N`.
7. Final chat message: what was done, what is verified, what is next, anything needing the human.

## 2. Stack (locked; do not swap without a Decisions-log entry)

- Backend: Python 3.12, Django 5.x, Django REST Framework. One Django project per service.
- Package manager: `uv` (workspace at `backend/`). Lockfile `backend/uv.lock` is committed.
- API docs: `drf-spectacular` (OpenAPI 3 at `/docs`, schema at `/schema`). Security: `django-cors-headers`, DRF throttling on auth routes, body size limit.
- PostgreSQL 16 via the Django ORM + `django.contrib.postgres`. Search uses `SearchVector`/`SearchQuery` and `GinIndex` — SQL-level FTS, never in-Python filtering (I4).
- Migrations: Django migrations (Python). Immutable once committed (I5).
- Kafka via `confluent-kafka` (librdkafka); broker is `apache/kafka` (KRaft, single node). Idempotent producer, `acks=all`.
- Auth: argon2id (`argon2-cffi`, Django default hasher) and `djangorestframework-simplejwt` (asymmetric ES256/RS256; peer public key from env).
- Background workers (relay, consumer, reconciler) are Django management commands run as separate containers. No Celery, no extra broker.
- Config: `pydantic-settings`, one settings package per service, fail fast on missing env at boot.
- Logging: stdlib `logging` with a JSON formatter and redaction. Tests: `pytest` + `pytest-django`. Lint + format: `ruff`; types: `mypy`.
- WSGI server: `gunicorn`. Frontend: Vite + React + TypeScript.
- Packaging: Docker multi-stage, base `python:3.12-slim`, non-root. Reverse proxy: Caddy. CI/CD: GitHub Actions + GHCR + SSH deploy.

## 3. Repository layout

```
AGENTS.md CONTEXT.md ARCHITECTURE.md README.md Makefile tasks.ps1 opencode.json
docs/                      ASSIGNMENT.md PROPOSAL.md API.md search-performance.md outage-recovery.md runbook.md deployment.md
backend/                   pyproject.toml uv.lock
backend/packages/contracts/    event envelope + pydantic schemas + topic names ONLY. No runtime logic, no DB, no HTTP.
backend/services/job-service/        Django project: config/ apps/ migrations/ tests/ Dockerfile   (port 3001)
backend/services/candidate-service/  Django project: config/ apps/ migrations/ tests/ Dockerfile   (port 3002)
frontend/                  Vite + React + TypeScript app
e2e/                       outage/recovery scenarios (the only place allowed to read both DBs)
scripts/                   seed_jobs.py replay_dlq.py demo_kafka_outage.sh explain_analyze.sh smoke.sh
deploy/                    docker-compose.dev.yml docker-compose.prod.yml Caddyfile scripts/ .env.example
.github/workflows/         ci.yml deploy.yml
```

Inside a service: `config/{settings,urls,asgi,wsgi}.py`, `apps/<feature>/{models,serializers,views,services,repo}.py`, `apps/<feature>/management/commands/` for background workers. Routes are thin; logic lives in `apps/*/services.py`; SQL-heavy queries live in `apps/*/repo.py`.

## 4. Hard invariants (violating any of these is a failed task)

- **I1. Database ownership.** A service never connects to the other service's database, and never imports the other service's code. Cross-service data flows only via Kafka events or HTTP APIs. The sole exception is read-only assertions inside `e2e/`.
- **I2. Outbox only.** Domain events are written to `outbox_events` **in the same DB transaction** as the state change. Request handlers never call the Kafka producer directly. Only the relay publishes.
- **I3. Idempotent, order-safe consumers.** Every handler must be safe under duplicate delivery, redelivery and out-of-order delivery. Apply an event only if `incoming.version > stored.version`. Record `event_id` in `processed_events` in the same transaction as the effect.
- **I4. Search in SQL.** Search uses `tsvector`/`tsquery` + GIN, with `LIMIT/OFFSET` in SQL. Never fetch rows into memory and filter in JS.
- **I5. Migrations are immutable once committed.** Change schema with a new migration. Keep migrations backward compatible (expand/contract) so app rollback stays safe.
- **I6. No secrets in git, images, or logs.** Use env vars; `.env.example` has placeholders only; pino `redact` for `authorization`, `password`, tokens.
- **I7. Uniqueness in the database.** "One application per candidate per job" is enforced by a `UNIQUE (candidate_id, job_id)` constraint; the app maps SQLSTATE `23505` to HTTP 409.
- **I8. Internal endpoints are never public.** Anything under `/internal/*` requires `X-Internal-Token` and is blocked at Caddy.
- **I9. Kafka is optional for availability.** Neither service may refuse to start, serve HTTP, or fail `/readyz` because Kafka is down. Kafka connectivity is retried in the background and reported as `degraded`.

## 5. Commands

All must exist after M1. If one is missing, create it; do not work around it. On Windows, `tasks.ps1` provides the same targets (run `./tasks.ps1 infra-up`).

```
make infra-up / infra-down     # kafka + 2 postgres (docker compose, deploy/docker-compose.dev.yml)
make migrate                   # migrate both DBs independently (manage.py migrate per service)
make dev                       # run both services with watch mode
make verify                    # lint (ruff) + typecheck (mypy) + unit + integration tests (pytest)  <- run before every commit batch and at session end
make e2e                       # outage/recovery scenarios (needs infra-up)
make seed N=100000             # seed jobs for search benchmarks
make explain                   # EXPLAIN (ANALYZE, BUFFERS) for the benchmark queries
make openapi                   # dump OpenAPI JSON for both services into docs/
make prod-local                # run the prod compose locally behind Caddy (tls internal)
```

## 6. Code conventions

- Error responses: `{ "error": { "code": "APPLICATION_ALREADY_EXISTS", "message": "...", "details": {} } }` with correct HTTP status. Codes are SCREAMING_SNAKE and documented in OpenAPI.
- Validate every input with a DRF serializer (or a pydantic schema in `packages/contracts`). Never interpolate user input into SQL; use the ORM or parameterized `cursor.execute(sql, params)`.
- IDs are UUIDs (`gen_random_uuid()`); timestamps are `timestamptz`; event timestamps are ISO-8601 UTC strings.
- Pagination: `page` (1-based) and `pageSize` (default 20, max 50); responses `{ items, page, pageSize, total }`.
- Config: one `pydantic-settings` settings object per service; fail fast on missing env at boot.
- Every background worker (relay, consumer, reconciler) logs structured events: `{ component, event, ...ids }`, and exposes state via `/internal/admin/*`.
- Prefer boring, readable code. No premature abstractions, no extra frameworks, no UI.

## 7. Definition of done (per milestone)

1. Every checklist item ticked **with evidence** (acceptance command passed).
2. `make verify` green; new behavior has tests (reliability paths: tests mandatory).
3. No invariant (I1-I9) violated; no TODO left without a CONTEXT.md entry.
4. CONTEXT.md updated per "END" above.

## 8. Scope control

- Do not add features not in the assignment (email, file uploads, payments, social login). **Exception:** the React frontend is explicitly approved by the human; see the entry in CONTEXT.md > Decisions log.
- Optional items are marked `(P1)` in CONTEXT.md; do them only after all non-P1 items of the milestone pass.
- If the assignment and ARCHITECTURE.md conflict, the assignment wins; record it in the Decisions log and fix ARCHITECTURE.md.

## 9. Keeping the docs alive

- `CONTEXT.md` is **append-mostly project memory**: it is the handoff to the next session, which has zero memory of this one. Write for a stranger: concrete file paths, exact commands, exact error messages.
- If implementation diverges from `ARCHITECTURE.md`, update `ARCHITECTURE.md` in the same commit and note it in Decisions.
- Prune Gotchas that proved wrong (mark `~~struck~~ (wrong: reason)`; do not silently delete).

## 10. Skills

`.opencode/skills/` holds reusable skills. Load a skill with the `skill` tool when the task matches its description. Do not load unrelated skills.

Relevant to this project:

- `skill-creator` — create or improve a skill.
- `mcp-builder` — build an MCP server.
- `doc-coauthoring` — write docs, proposals, specs (use for `docs/PROPOSAL.md`).
- `frontend-design` — visual direction for the React frontend.
- `webapp-testing` — drive the frontend in a browser for checks.

Out of scope for this project (do not load): `pptx`, `xlsx`, `docx`, `pdf`, `slack-gif-creator`, `canvas-design`, `algorithmic-art`, `theme-factory`, `brand-guidelines`, `internal-comms`, `claude-api`, `mcp-builder` unless an MCP task appears.
