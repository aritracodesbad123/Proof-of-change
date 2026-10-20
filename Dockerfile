# Proof-of-Change operator console (SPA + /api).
# Works on: local, Render free, Hugging Face Spaces (Docker SDK), Nebius Endpoint.
#
#   docker build -t poc-console:local .
#   docker run -e PORT=7860 -p 7860:7860 poc-console:local
#   Render sets PORT=8787 (render.yaml). Spaces sets PORT=7860.
# The process runs as uid 1000. Writes go under $HOME (Spaces disk is ephemeral).

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY console/web/package.json console/web/package-lock.json ./
RUN npm ci
COPY console/web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
# chromium: headless PDF for golden-format REPORT.pdf (reports/reviewer.to_pdf)
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    git curl ca-certificates bubblewrap \
    chromium fonts-liberation fonts-dejavu-core \
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

RUN pip install --no-cache-dir -e ".[ops,contree]"

# Hugging Face Spaces starts the container as uid 1000 and only $HOME and /tmp are writable.
RUN groupadd --gid 1000 user \
    && useradd --uid 1000 --gid 1000 --create-home --home-dir /home/user user \
    && mkdir -p /home/user/poc/runs /home/user/poc/work /home/user/poc/reports /tmp/poc \
    && chown -R user:user /home/user /app
USER 1000
ENV HOME=/home/user \
    POC_CONSOLE_HOST=0.0.0.0 \
    POC_OPS_RUNS=/home/user/poc/runs \
    POC_OPS_DIR=/home/user/poc \
    POC_REPORT_DIR=/home/user/poc/reports \
    POC_ACCOUNTS_FILE=/home/user/poc/console-accounts.json \
    TMPDIR=/tmp \
    PYTHONUNBUFFERED=1 \
    BR_CHROME=/usr/bin/chromium

EXPOSE 7860
EXPOSE 8787
# PORT comes from the host: 7860 on a Space, 8787 on Render. Shell form so it expands.
CMD python -m poc.console_api --host 0.0.0.0 --port "${PORT:-8787}"
