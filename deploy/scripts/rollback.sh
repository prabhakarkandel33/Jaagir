#!/usr/bin/env bash
# Roll back to a previously deployed image tag.
#
#   ./deploy/scripts/rollback.sh [tag]
#
# With no argument it uses `.previous_tag`, which deploy.sh writes before it
# changes anything. Schema changes are expand/contract, so the older code runs
# against the newer schema.
set -euo pipefail

TAG="${1:-}"
APP_DIR="${APP_DIR:-/opt/jobportal}"
ENV_FILE="${ENV_FILE:-${APP_DIR}/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${APP_DIR}/deploy/docker-compose.prod.yml}"

if [[ -z "${TAG}" ]]; then
  if [[ -s "${APP_DIR}/.previous_tag" ]]; then
    TAG="$(tr -d '[:space:]' <"${APP_DIR}/.previous_tag")"
  fi
fi
if [[ -z "${TAG}" ]]; then
  echo "usage: rollback.sh <tag>   (no .previous_tag found)" >&2
  exit 1
fi

cd "${APP_DIR}"
echo "rollback: switching to ${TAG}"
IMAGE_TAG="${TAG}" docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --remove-orphans

for service in job-service candidate-service; do
  deadline=$((SECONDS + 90))
  healthy=0
  while ((SECONDS < deadline)); do
    id="$(IMAGE_TAG="${TAG}" docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps -q "${service}" 2>/dev/null || true)"
    status=""
    if [[ -n "${id}" ]]; then
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${id}" 2>/dev/null || true)"
    fi
    if [[ "${status}" == "healthy" ]]; then
      echo "rollback: ${service} healthy"
      healthy=1
      break
    fi
    sleep 3
  done
  if [[ "${healthy}" -ne 1 ]]; then
    echo "rollback: ${service} did not become healthy; manual action required" >&2
    exit 1
  fi
done

if grep -qE '^IMAGE_TAG=' "${ENV_FILE}"; then
  sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=${TAG}|" "${ENV_FILE}"
fi
echo "rollback: ${TAG} is live"
