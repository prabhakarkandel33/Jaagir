# Production image for the Candidate & Application Service.
#
# Build context is the REPOSITORY ROOT (the workspace lockfile and the shared
# contracts package live under backend/):
#
#   docker build -f backend/services/candidate-service/Dockerfile \
#     -t jobportal/candidate-service:local .
#
# Multi-stage: build the virtualenv in a builder and copy only the runtime
# files. Runs as an unprivileged user and serves WSGI through gunicorn.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /bin/

WORKDIR /app

# Dependency layer first: a source edit does not reinstall the workspace.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
COPY backend/packages/contracts/pyproject.toml packages/contracts/
# The contracts wheel is built during `uv sync`, so its source must exist first.
COPY backend/packages/contracts/src packages/contracts/src
COPY backend/services/job-service/pyproject.toml services/job-service/
COPY backend/services/candidate-service/pyproject.toml services/candidate-service/
RUN uv sync --all-packages --frozen --no-dev --no-editable

COPY backend/ ./

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    MEDIA_ROOT=/app/media

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /app /app
RUN mkdir -p /app/media && chown app:app /app/media

USER app
WORKDIR /app/services/candidate-service

EXPOSE 3002

# Production settings redirect plain HTTP to HTTPS, so the probe sends
# X-Forwarded-Proto (the same header Caddy sets in front of the service).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request as u; r=u.urlopen(u.Request('http://127.0.0.1:3002/healthz', headers={'X-Forwarded-Proto': 'https'}), timeout=3); raise SystemExit(0 if r.status == 200 else 1)"

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:3002", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
