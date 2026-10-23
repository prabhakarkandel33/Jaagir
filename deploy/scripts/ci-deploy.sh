#!/usr/bin/env bash
# Forced-command deploy entry point for the VPS.
#
# SSH passes the requested commit as $SSH_ORIGINAL_COMMAND. That value is
# hostile input: accept exactly one lowercase 40-character SHA and nothing else.
# Never eval it.
#
#   ssh deploy@vps <sha>                 # forced command, real deploy
#   ./ci-deploy.sh --dry-run <sha>       # local check, no checkout/build/deploy
#
# The script builds the exact SHA on the VPS, then calls deploy.sh so the
# previous image tag remains on disk for rollback.
set -euo pipefail

readonly APP_DIR="/opt/jobportal"
readonly REPO_DIR="${APP_DIR}/repo"
readonly ENV_FILE="${APP_DIR}/.env"
readonly COMPOSE_FILE="${REPO_DIR}/deploy/docker-compose.prod.yml"
readonly LOCK_FILE="${APP_DIR}/.deploy.lock"
readonly LOG_FILE="/var/log/jobportal-deploy.log"

DRY_RUN=0
SHA=""

fail() {
  printf 'ci-deploy: %s\n' "$*" >&2
  exit 2
}

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "${LOG_FILE}" >&2
}

parse_args() {
  local raw="${SSH_ORIGINAL_COMMAND:-}"

  if [[ -n "${raw}" ]]; then
    if [[ "${raw}" =~ ^--dry-run[[:space:]]+([0-9a-f]{40})$ ]]; then
      DRY_RUN=1
      SHA="${BASH_REMATCH[1]}"
    elif [[ "${raw}" =~ ^([0-9a-f]{40})$ ]]; then
      SHA="${BASH_REMATCH[1]}"
    else
      fail "invalid SSH command; expected a 40-character lowercase SHA"
    fi
  else
    if (( $# == 0 )); then
      fail "usage: ci-deploy.sh [--dry-run] <40-character-sha>"
    fi
    if [[ "$1" == "--dry-run" ]]; then
      DRY_RUN=1
      shift
    fi
    if (( $# != 1 )); then
      fail "usage: ci-deploy.sh [--dry-run] <40-character-sha>"
    fi
    SHA="$1"
  fi

  if [[ ! "${SHA}" =~ ^[0-9a-f]{40}$ ]]; then
    fail "invalid SHA; expected 40 lowercase hexadecimal characters"
  fi
}

parse_args "$@"

if ! touch "${LOG_FILE}" 2>/dev/null; then
  printf 'ci-deploy: cannot write %s\n' "${LOG_FILE}" >&2
  exit 1
fi

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  log "another deploy is running; refusing to start"
  exit 1
fi

cd "${REPO_DIR}"

# deploy.sh writes its rollback pointer to ${APP_DIR}/.previous_tag. APP_DIR is
# the repo, so that expected untracked file must not count as a dirty worktree.
DIRTY="$(git status --porcelain)"
DIRTY="$(printf '%s\n' "${DIRTY}" | grep -v -x -F -- '?? .previous_tag' || true)"
if [[ -n "${DIRTY}" ]]; then
  log "refusing to deploy: ${REPO_DIR} has uncommitted changes"
  exit 1
fi

if ! git fetch --quiet origin main; then
  log "git fetch origin main failed"
  exit 1
fi

if ! git merge-base --is-ancestor "${SHA}" origin/main; then
  log "refusing to deploy ${SHA}: it is not an ancestor of origin/main"
  exit 1
fi

if (( DRY_RUN == 1 )); then
  log "dry-run ok: ${SHA} is on origin/main; no checkout, build or deploy"
  exit 0
fi

if ! git checkout --quiet --detach "${SHA}"; then
  log "git checkout --detach ${SHA} failed"
  exit 1
fi

CURRENT_TAG="$(grep -m1 '^IMAGE_TAG=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2- || true)"
CURRENT_TAG="${CURRENT_TAG%$'\r'}"
CURRENT_TAG="${CURRENT_TAG//[^A-Za-z0-9._-]/}"
CURRENT_TAG="${CURRENT_TAG:0:64}"

log "deploy start: ${SHA} (previous image tag: ${CURRENT_TAG:-none})"

if ! IMAGE_TAG="${SHA}" docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" build 2>&1 |
  while IFS= read -r line; do log "${line}"; done; then
  log "image build failed for ${SHA}"
  exit 1
fi

if ! env APP_DIR="${REPO_DIR}" ENV_FILE="${ENV_FILE}" bash "${REPO_DIR}/deploy/scripts/deploy.sh" "${SHA}" 2>&1 |
  while IFS= read -r line; do log "${line}"; done; then
  log "deploy failed for ${SHA}; deploy.sh reports rollback separately"
  exit 1
fi

log "deploy complete: ${SHA}"
