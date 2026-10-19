# Job Portal - top-level commands (AGENTS.md section 5).
# On Windows use `tasks.ps1` instead: ./tasks.ps1 <target>

BACKEND  := backend
JOB      := $(BACKEND)/services/job-service
CAND     := $(BACKEND)/services/candidate-service
CONTRACTS:= $(BACKEND)/packages/contracts
COMPOSE  := docker compose -f deploy/docker-compose.dev.yml
COMPOSE_FULL := docker compose -f deploy/docker-compose.dev-full.yml
N        ?= 100000
BUILD    ?=

.PHONY: help sync infra-up infra-down stack-up stack-down stack-logs stack-ps \
        migrate dev dev-job dev-candidate \
        lint typecheck test verify openapi seed explain e2e prod-local

help:
	@echo "targets:"
	@echo "  infra-up / infra-down   kafka + 2 postgres (deploy/docker-compose.dev.yml)"
	@echo "  stack-up                whole stack in docker (BUILD=1 to rebuild images)"
	@echo "  stack-down / stack-logs / stack-ps"
	@echo "  sync                    uv sync --all-packages"
	@echo "  migrate                 migrate both DBs independently"
	@echo "  dev                     run both services (watch mode)"
	@echo "  verify                  lint + typecheck + unit + integration tests"
	@echo "  openapi                 dump OpenAPI JSON for both services into docs/"
	@echo "  seed N=100000           seed jobs for search benchmarks (M5)"
	@echo "  explain                 EXPLAIN (ANALYZE, BUFFERS) benchmark (M5)"
	@echo "  e2e                     outage/recovery scenarios (M6)"
	@echo "  prod-local              prod compose behind Caddy (M7)"

sync:
	cd $(BACKEND) && uv sync --all-packages

infra-up:
	$(COMPOSE) up -d --wait

infra-down:
	$(COMPOSE) down

stack-up:
	$(COMPOSE_FULL) up -d --wait $(if $(BUILD),--build,)

stack-down:
	$(COMPOSE_FULL) down

stack-logs:
	$(COMPOSE_FULL) logs -f

stack-ps:
	$(COMPOSE_FULL) ps

migrate:
	cd $(JOB) && uv run python manage.py migrate
	cd $(CAND) && uv run python manage.py migrate

dev-job:
	cd $(JOB) && uv run python manage.py runserver 3001

dev-candidate:
	cd $(CAND) && uv run python manage.py runserver 3002

dev:
	$(MAKE) -j2 dev-job dev-candidate

lint:
	cd $(BACKEND) && uv run ruff check .
	cd $(BACKEND) && uv run ruff format --check .

typecheck:
	cd $(BACKEND) && uv run mypy packages/contracts/src
	cd $(JOB) && uv run mypy --config-file mypy.ini .
	cd $(CAND) && uv run mypy --config-file mypy.ini .

test:
	cd $(CONTRACTS) && uv run pytest -q
	cd $(JOB) && uv run pytest -q
	cd $(CAND) && uv run pytest -q

verify: lint typecheck test

openapi:
	mkdir -p docs
	cd $(JOB) && uv run python manage.py spectacular --file ../../../docs/openapi-job-service.json
	cd $(CAND) && uv run python manage.py spectacular --file ../../../docs/openapi-candidate-service.json

seed:
	uv run --project backend python scripts/seed_jobs.py --service job --count $(N)
	uv run --project backend python scripts/seed_jobs.py --service candidate --count $(N)

explain:
	uv run --project backend python scripts/explain_analyze.py --service job
	uv run --project backend python scripts/explain_analyze.py --service candidate

e2e:
	@echo "make e2e: not implemented yet (M6)"

prod-local:
	@echo "make prod-local: not implemented yet (M7)"
