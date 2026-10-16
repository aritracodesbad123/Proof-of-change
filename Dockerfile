# Proof-of-Change operator console (SPA + /api).
# Works on: local, Render free, Nebius Endpoint, any Docker host.
#
#   docker build -t poc-console:local .
#   make docker-console IMAGE=…   /   make nebius-console …
#   Render: connect this repo (render.yaml) — free tier

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY console/web/package.json console/web/package-lock.json ./
RUN npm ci
COPY console/web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update \
  && apt-get install -y --no-install-recommends git curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY poc/ poc/
COPY harness/ harness/
COPY evals/ evals/
COPY guardrails/ guardrails/
COPY reports/ reports/
COPY ops/ ops/
COPY --from=web /web/dist console/web/dist

RUN pip install --no-cache-dir -e ".[ops]"

ENV POC_CONSOLE_HOST=0.0.0.0 \
    POC_CONSOLE_PORT=8787 \
    PORT=8787 \
    PYTHONUNBUFFERED=1

EXPOSE 8787
# Render / many PaaS set PORT; Nebius uses 8787. Shell form so ${PORT} expands.
CMD python -m poc.console_api --host 0.0.0.0 --port "${PORT:-8787}"
