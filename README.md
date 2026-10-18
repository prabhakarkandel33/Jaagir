# Job Portal

Two Kafka-connected microservices on PostgreSQL, with a React frontend.

| Component | Stack | Port |
|---|---|---|
| Job Service | Django 5 + DRF | 3001 |
| Candidate & Application Service | Django 5 + DRF | 3002 |
| Frontend | Vite + React + TypeScript | 5173 |
| Job DB | PostgreSQL 16 | 5433 |
| Candidate DB | PostgreSQL 16 | 5434 |
| Kafka | apache/kafka (KRaft, single node) | 9092 |

Requirements source of truth: `docs/ASSIGNMENT.md`.
Design: `ARCHITECTURE.md`. Work queue and status: `CONTEXT.md`. Agent rules: `AGENTS.md`.

## Status

Scaffold in progress (M1). See `CONTEXT.md` > Status board.

## Local setup

See `AGENTS.md` section 5 for the full command list. On Windows, use `tasks.ps1` (same targets).
