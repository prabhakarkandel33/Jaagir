#!/usr/bin/env bash
# One-time VPS bootstrap for the Job Portal (Ubuntu 24.04/22.04).
#
#   sudo DEPLOY_USER=deploy ./deploy/scripts/bootstrap-vps.sh
#
# Installs Docker Engine + Compose plugin, creates the deploy user and app
# directories, and enables a deny-by-default firewall with only 22/80/443 open.
# Idempotent: safe to run again.
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
APP_DIR="${APP_DIR:-/opt/jobportal}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root (sudo)" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg ufw

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
apt-get install -y --no-install-recommends docker-compose-plugin
systemctl enable --now docker

if ! id -u "${DEPLOY_USER}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "${DEPLOY_USER}"
fi
usermod -aG docker "${DEPLOY_USER}"

install -d -m 0750 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${APP_DIR}"
install -d -m 0750 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${APP_DIR}/backups"

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "bootstrap complete"
echo "next: install the CI public key for ${DEPLOY_USER}, then run deploy/scripts/render-env.sh"
echo "check: docker version && docker compose version && ufw status"
