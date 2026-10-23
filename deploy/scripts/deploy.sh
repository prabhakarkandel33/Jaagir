#!/usr/bin/env bash
# Deploy an image tag to the VPS with a health gate and automatic rollback.
#
#   ./deploy/scripts/deploy.sh <git-sha-tag>
#
# 1. remembers the current tag in .previous_tag
# 2. pulls the new images and runs both migration jobs
# 3. starts the stack and waits for both web containers to report healthy
# 4. on any failure, calls rollback.sh with the previous tag
#
# Migrations must stay expand/contract (invariant I5) so the previous tag can
# still run after a failed deploy.
set -euo pipefail

TAG="${1:-}"
APP_DIR="${APP_DIR:-/opt/jobportal}"
ENV_FILE="${ENV_FILE:-${APP_DIR}/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${APP_DIR}/deploy/docker-compose.prod.yml}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"

if [[ -z "${TAG}" ]]; then
  echo "usage: deploy.sh <tag>" >&2
  exit 1
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "deploy: missing ${ENV_FILE}; run render-env.sh first" >&2
  exit 1
fi

cd "${APP_DIR}"
dc() { docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"; }

CURRENT_TAG="$(grep -E '^IMAGE_TAG=' "${ENV_FILE}" | head -n1 | cut -d= -f2- || true)"
CURRENT_TAG="${CURRENT_TAG//\'/}"
printf '%s\n' "${CURRENT_TAG}" >"${APP_DIR}/.previous_tag"

export IMAGE_TAG="${TAG}"

rollback() {
  if [[ "${ROLLBACK_IN_PROGRESS:-0}" == "1" ]]; then
    echo "deploy: rollback already in progress; stopping" >&2
    exit 1
  fi
  if [[ -z "${CURRENT_TAG}" || "${CURRENT_TAG}" == "${TAG}" ]]; then
    echo "deploy: no usable previous tag; manual action required" >&2
    exit 1
  fi
  echo "deploy: health gate failed, rolling back to ${CURRENT_TAG}" >&2
  ROLLBACK_IN_PROGRESS=1 bash "${APP_DIR}/deploy/scripts/rollback.sh" "${CURRENT_TAG}" || true
  exit 1
}

wait_healthy() {
  local service="$1" deadline=$((SECONDS + HEALTH_TIMEOUT)) id status
  while ((SECONDS < deadline)); do
    id="$(dc ps -q "${service}" 2>/dev/null || true)"
    if [[ -n "${id}" ]]; then
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${id}" 2>/dev/null || true)"
      if [[ "${status}" == "healthy" ]]; then
        echo "deploy: ${service} healthy"
        return 0
      fi
    fi
    sleep 3
  done
  echo "deploy: ${service} did not become healthy within ${HEALTH_TIMEOUT}s" >&2
  return 1
}

echo "deploy: tag ${TAG} (previous: ${CURRENT_TAG:-none})"

dc pull || echo "deploy: pull skipped/failed (local build?)"

# Databases first, then schema, then the rest of the stack.
dc up -d job-db candidate-db || rollback
dc run --rm job-migrate || rollback
dc run --rm candidate-migrate || rollback
dc up -d --remove-orphans || rollback

wait_healthy job-service || rollback
wait_healthy candidate-service || rollback

# Persist the tag only after the gate passes.
if grep -qE '^IMAGE_TAG=' "${ENV_FILE}"; then
  sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=${TAG}|" "${ENV_FILE}"
else
  printf 'IMAGE_TAG=%s\n' "${TAG}" >>"${ENV_FILE}"
fi

echo "deploy: ${TAG} is live"
