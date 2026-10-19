# Job Portal - top-level commands (AGENTS.md section 5).
# On Windows use `tasks.ps1` instead: ./tasks.ps1 <target>

BACKEND  := backend
JOB      := $(BACKEND)/services/job-service
CAND     := $(BACKEND)/services/candidate-service
CONTRACTS:= $(BACKEND)/packages/contracts
COMPOSE  := docker compose -f deploy/docker-compose.dev.yml
N        ?= 100000

.PHONY: help sync infra-up infra-down migrate dev dev-job dev-candidate \
        lint typecheck test verify openapi seed explain e2e prod-local

help:
	@echo "targets:"
	@echo "  infra-up / infra-down   kafka + 2 postgres (deploy/docker-compose.dev.yml)"
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
	@echo "make seed: not implemented yet (M5). N=$(N)"

explain:
	@echo "make explain: not implemented yet (M5)"

e2e:
	@echo "make e2e: not implemented yet (M6)"

prod-local:
	@echo "make prod-local: not implemented yet (M7)"
