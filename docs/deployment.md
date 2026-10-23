# Deployment

The Job Portal runs as one Docker Compose stack on a single VPS. Caddy is the
only container with public ports. Postgres, Kafka and both Django services stay
on a private Docker network.

## 1. Topology

| Domain | Container | Purpose |
|---|---|---|
| `jobs.<domain>` | `job-service:3001` | Recruiter API, public job search, outbox |
| `candidates.<domain>` | `candidate-service:3002` | Candidate API, search replica, applications |
| `app.<domain>` | `frontend:8080` | React portal (public site, portals, `/admin`) |

`/internal/*` returns 404 at Caddy. The candidate service calls the Job
Service over the compose network with `X-Internal-Token`.

Workers run as separate containers from the same images:

- `job-relay` publishes outbox rows.
- `candidate-consumer` applies Kafka events.
- `candidate-reconciler` repairs the replica.

## 2. Prerequisites

- Ubuntu 24.04 LTS (22.04 also works), 4 vCPU, 8 GB RAM, 80 GB SSD.
- Three DNS A/AAAA records that resolve to the VPS **before** the first deploy:
  `jobs`, `candidates`, `app`.
- Ports 22, 80 and 443 open. Nothing else is public.
- Docker Engine + Compose plugin (the bootstrap script installs them).
- A deploy user with Docker permissions and the CI public key in
  `~/.ssh/authorized_keys`.
- Images in a registry (GHCR) or built on the host.

## 3. Bootstrap the VPS

```bash
sudo DEPLOY_USER=deploy bash deploy/scripts/bootstrap-vps.sh
```

This installs Docker, creates `/opt/jobportal`, and enables UFW with only SSH,
HTTP and HTTPS. Copy the repository to `/opt/jobportal` (or clone it there) so
`deploy/docker-compose.prod.yml` and the service Dockerfiles are present.

## 4. Secrets

`deploy/scripts/render-env.sh` reads values from the environment and writes
`/opt/jobportal/.env` with mode 600. It never prints values. Required inputs:

| Variable | Meaning |
|---|---|
| `DJANGO_SECRET_KEY` | 50+ random characters |
| `INTERNAL_TOKEN` | 32+ random bytes (shared by both services) |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | `/admin` console login |
| `JOB_DB_PASSWORD`, `CANDIDATE_DB_PASSWORD` | database passwords (URL-safe) |
| `JOB_DOMAIN`, `CANDIDATE_DOMAIN`, `FRONTEND_DOMAIN` | DNS names |
| `JOB_JWT_SIGNING_KEY`, `JOB_JWT_PUBLIC_KEY` | base64 PEM keypair (job) |
| `CANDIDATE_JWT_SIGNING_KEY`, `CANDIDATE_JWT_PUBLIC_KEY` | base64 PEM keypair (candidate) |
| `ACME_EMAIL` | optional Let's Encrypt contact email |

Optional: `JOB_PUBLIC_URL`, `CANDIDATE_PUBLIC_URL`, `FRONTEND_PUBLIC_URL`,
`ALLOWED_HOSTS`, `SECURE_HSTS_SECONDS` (use `0` for a local trial),
`LOG_LEVEL`, `JOB_IMAGE`, `CANDIDATE_IMAGE`, `FRONTEND_IMAGE`, `IMAGE_TAG`.

Generate an ES256 keypair and base64-encode it (repeat for the candidate
service):

```bash
uv run --no-project --with cryptography python - <<'PY'
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

key = ec.generate_private_key(ec.SECP256R1())
private = key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
public = key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()
print("SIGNING=" + base64.b64encode(private.encode()).decode())
print("PUBLIC=" + base64.b64encode(public.encode()).decode())
PY
```

The candidate service also receives the Job Service **public** key as
`JOB_SERVICE_JWT_PUBLIC_KEY`; the compose file maps it from
`JOB_JWT_PUBLIC_KEY`.

Required GitHub Environment secrets (for the deploy workflow, which is not
committed yet): `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`, the variables above,
and a GHCR token if the packages are private. Required variables:
`JOB_DOMAIN`, `CANDIDATE_DOMAIN`, `FRONTEND_DOMAIN`, image names under GHCR.

## 5. First deploy

```bash
cd /opt/jobportal
export IMAGE_TAG=latest
bash deploy/scripts/render-env.sh /opt/jobportal/.env
bash deploy/scripts/deploy.sh "$IMAGE_TAG"
```

`deploy.sh` saves the current tag, pulls images, runs both migration jobs,
starts the stack, and waits for both web containers to become healthy. On
failure it rolls back automatically.

After the first deploy, check:

```bash
curl -fsS https://jobs.<domain>/readyz
curl -fsS https://candidates.<domain>/readyz
curl -s -o /dev/null -w '%{http_code}\n' https://jobs.<domain>/internal/admin/outbox  # 404
```

## 6. Local production trial

```bash
./tasks.ps1 prod-local      # Windows
make prod-local             # Linux/macOS
```

This copies `deploy/.env.prod.example` to `deploy/.env.prod` when missing,
builds both service images and the frontend, and starts the stack behind Caddy
on host ports 8080/8443 (`https://app.localhost:8443`, `https://jobs.localhost:8443`,
`https://candidates.localhost:8443`) with an internal CA.

Open `https://app.localhost:8443` and accept the certificate warning. API
checks:

```bash
curl -k https://jobs.localhost:8443/readyz
curl -k https://candidates.localhost:8443/readyz
curl -k -o /dev/null -w '%{http_code}\n' https://jobs.localhost:8443/internal/admin/outbox
```

The example file has empty JWT keys, so authentication does not work until you
fill them in (section 4). Health and the public job browse page work without
them.

Stop with `./tasks.ps1 prod-down` or `make prod-down`.

## 7. Images

Each backend image builds from the repository root because the workspace
lockfile and `packages/contracts` live under `backend/`:

```bash
docker build -f backend/services/job-service/Dockerfile -t jobportal/job-service:dev .
docker build -f backend/services/candidate-service/Dockerfile -t jobportal/candidate-service:dev .
docker build -f frontend/Dockerfile \
  --build-arg VITE_JOB_SERVICE_URL=https://jobs.<domain> \
  --build-arg VITE_CANDIDATE_SERVICE_URL=https://candidates.<domain> \
  -t jobportal/frontend:dev frontend
```

The backend images are multi-stage, run as uid 10001, and serve gunicorn with
two workers. The frontend image runs nginx as uid 101 on port 8080. Vite
inlines the API URLs at build time, so a domain change needs a frontend
rebuild.

## 8. Rollback

```bash
bash deploy/scripts/rollback.sh              # uses .previous_tag
bash deploy/scripts/rollback.sh <tag>        # explicit
```

Migrations are expand/contract, so the previous application version runs
against the current schema. Do not remove a column or rename a table in the
same release that stops writing it.

## 9. Backups

```bash
bash deploy/scripts/backup-db.sh
```

Writes compressed `pg_dump` files for both databases plus a tar of the CV media
volume into `/opt/jobportal/backups`, keeps 7 days, and sets mode 600. Add it
to cron:

```cron
15 2 * * * bash /opt/jobportal/deploy/scripts/backup-db.sh >>/var/log/jobportal-backup.log 2>&1
```

Restore (example, candidate DB):

```bash
gunzip -c backups/candidate_db-<stamp>.sql.gz \
  | docker compose --env-file .env -f deploy/docker-compose.prod.yml \
      exec -T candidate-db psql -U jobportal -d candidate_db
```

## 10. Operations

```bash
docker compose --env-file .env -f deploy/docker-compose.prod.yml ps
docker compose --env-file .env -f deploy/docker-compose.prod.yml logs -f --tail=200
```

| Symptom | Check | Action |
|---|---|---|
| Jobs not reaching candidates | `/internal/admin/outbox` on jobs domain | Kafka down? Relay logs. Rows drain when Kafka returns |
| Replica drift | `/internal/admin/sync-status` on candidates domain | `POST /internal/admin/reconcile?mode=full` with the internal token |
| Poison event | DLQ topic / consumer logs | Fix the cause, then run `scripts/replay_dlq.py` or the admin replay endpoint |
| Certificates missing | `docker compose logs caddy` | DNS must resolve; ports 80/443 open; ACME rate limit |
| 502 from Caddy | `docker compose ps` | Wait for web health or inspect gunicorn logs |
| CV download 404 | candidate logs | File absent on the `candidate_media` volume |

## 11. Security checklist

- `.env` is mode 600 and never committed.
- `/internal/*` is blocked at Caddy and still requires `X-Internal-Token`.
- Containers run as non-root; only Caddy publishes ports.
- Logs are rotated (`json-file`, 10 MB × 3 per container).
- Secrets are not baked into images; the frontend bundle contains only API URLs.
