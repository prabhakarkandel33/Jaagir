# Production image for the Jaagir workbench.
#
#   docker build -t jobportal-frontend \
#     --build-arg VITE_JOB_SERVICE_URL=https://jobs.example.com \
#     --build-arg VITE_CANDIDATE_SERVICE_URL=https://candidates.example.com .
#
# Stage 1 builds the static bundle with Node. Stage 2 serves it with the
# unprivileged nginx image (runs as uid 101, listens on 8080). Caddy terminates
# TLS in front of this container (M7).

FROM node:22-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

ARG VITE_JOB_SERVICE_URL=http://localhost:3001
ARG VITE_CANDIDATE_SERVICE_URL=http://localhost:3002
ENV VITE_JOB_SERVICE_URL=$VITE_JOB_SERVICE_URL \
    VITE_CANDIDATE_SERVICE_URL=$VITE_CANDIDATE_SERVICE_URL

RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1

USER 101
