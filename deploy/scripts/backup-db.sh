#!/usr/bin/env bash
# Nightly logical backup of both databases plus the CV media volume.
#
#   ./deploy/scripts/backup-db.sh [/opt/jobportal/backups]
#
# Keeps 7 days. Add to the deploy user's crontab:
#   15 2 * * * bash /opt/jobportal/deploy/scripts/backup-db.sh >>/var/log/jobportal-backup.log 2>&1
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/jobportal}"
ENV_FILE="${ENV_FILE:-${APP_DIR}/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${APP_DIR}/deploy/docker-compose.prod.yml}"
BACKUP_DIR="${1:-${APP_DIR}/backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "${BACKUP_DIR}"
cd "${APP_DIR}"
dc() { docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"; }

set -a
# shellcheck disable=SC1090
. "${ENV_FILE}"
set +a

dc exec -T job-db pg_dump -U "${JOB_DB_USER:-jobportal}" -d job_db \
  | gzip -9 >"${BACKUP_DIR}/job_db-${STAMP}.sql.gz"
dc exec -T candidate-db pg_dump -U "${CANDIDATE_DB_USER:-jobportal}" -d candidate_db \
  | gzip -9 >"${BACKUP_DIR}/candidate_db-${STAMP}.sql.gz"
dc exec -T candidate-service tar -czf - -C /app media \
  >"${BACKUP_DIR}/candidate_media-${STAMP}.tar.gz"

chmod 600 "${BACKUP_DIR}"/*-"${STAMP}".*
find "${BACKUP_DIR}" -type f -mtime "+${KEEP_DAYS}" -delete

echo "backup: wrote ${BACKUP_DIR}/*-${STAMP}.* (keeping ${KEEP_DAYS} days)"
