# Proof-of-Change: one-word commands. Type `make` to see them. Details: README.md and docs/OPERATIONS.md.
SHELL := /bin/bash
PYTHON ?= python3
VENV := .venv
PY := $(VENV)/bin/python
export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)

.DEFAULT_GOAL := help
.PHONY: help setup check daily open decide test golden-reports console console-api console-web console-build console-host docker-console nebius-console

help:
	@echo "Proof-of-Change commands:"
	@echo "  make setup                              one-time install (creates .venv)"
	@echo "  make check PR=<pull request link>       test one PR and write its report"
	@echo "  make daily                              the daily run over all tracked libraries"
	@echo "  make open                               open the newest report summary"
	@echo "  make console                            operator UI (API :8787 + Vite :5173)"
	@echo "  make console-api                        API only (http://127.0.0.1:8787)"
	@echo "  make console-web                        Vite UI only (proxies /api to :8787)"
	@echo "  make console-build                      build UI into console/web/dist (API can serve it)"
	@echo "  make console-host                       local: build + serve dist on 0.0.0.0:8787"
	@echo "  make docker-console IMAGE=…             build+push console container image"
	@echo "  make nebius-console IMAGE=… SUBNET_ID=… Nebius Endpoint (paid Compute)"
	@echo "  Free public URL: Render Blueprint (render.yaml) — see docs/OPERATIONS.md"
	@echo "  make decide REPORT=<folder> DECISION=approve|reject|approve_with_notes|re_run [NOTE=\"...\"]"
	@echo "  make test                               self-check: lint, guardrail, tests, evals"

setup:
	@$(PYTHON) -c 'import sys; v=sys.version_info; sys.exit(0 if v >= (3, 11) else "Python " + ".".join(map(str, v[:3])) + " is too old: Proof-of-Change needs Python 3.11 or newer. See README, setup step 2 (Install Python).")'
	@$(PYTHON) -c 'import sys; sys.path.insert(0, "."); from harness.machine import require_gxx; print("g++:", require_gxx())'
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -e ".[dev,ops]"
	@echo ""
	@echo "SETUP OK: Proof-of-Change is installed. Next: make check PR=<pull request link>"

$(PY):
	@echo "Not set up yet: run 'make setup' first." && exit 1

check: | $(PY)
	@test -n "$(PR)" || { echo 'Give the pull request link, e.g.: make check PR=https://github.com/pandas-dev/pandas/pull/12345'; exit 1; }
	$(PY) ops/daily_run.py --pr "$(PR)"

daily: | $(PY)
	$(PY) ops/daily_run.py

open:
	@f=$$(ls -t reports/daily/*/SUMMARY.html 2>/dev/null | head -1); \
	if [ -z "$$f" ]; then echo "No reports yet. Run: make check PR=<pull request link>"; exit 1; fi; \
	echo "Opening $(CURDIR)/$$f"; echo "(if no browser window appears, double-click that file in Finder)"; \
	if command -v open >/dev/null; then open "$$f"; elif command -v xdg-open >/dev/null; then xdg-open "$$f" || true; fi

console-api: | $(PY)
	$(PY) -m poc.console_api --host 127.0.0.1 --port 8787

console-web:
	@test -d console/web/node_modules || (cd console/web && npm install)
	cd console/web && npm run dev -- --host 127.0.0.1 --port 5173

console-build:
	@test -d console/web/node_modules || (cd console/web && npm install)
	cd console/web && npm run build

# Long-lived console on this machine: SPA from dist + /api on 0.0.0.0
console-host: console-build | $(PY)
	POC_CONSOLE_HOST=0.0.0.0 POC_CONSOLE_PORT=$${POC_CONSOLE_PORT:-8787} $(PY) -m poc.console_api --host 0.0.0.0 --port $${POC_CONSOLE_PORT:-8787}

# Container image for Nebius Serverless AI Endpoint (or any image host)
docker-console:
	@test -n "$(IMAGE)" || { echo 'Usage: make docker-console IMAGE=docker.io/<you>/poc-console:latest'; exit 1; }
	docker build -t "$(IMAGE)" .
	docker push "$(IMAGE)"

# Nebius Endpoint with --auth none → managed https://… URL (browser-navigable, like GCP)
nebius-console:
	@test -n "$(IMAGE)" -a -n "$(SUBNET_ID)" || { echo 'Usage: make nebius-console IMAGE=… SUBNET_ID=…  [NEBIUS_API_KEY=…]'; exit 1; }
	IMAGE="$(IMAGE)" SUBNET_ID="$(SUBNET_ID)" NAME="$(or $(NAME),poc-console)" \
	  NEBIUS_API_KEY="$(NEBIUS_API_KEY)" NEBIUS_PROJECT_ID="$(NEBIUS_PROJECT_ID)" POC_DEMO_REPOS="$(POC_DEMO_REPOS)" \
	  bash scripts/nebius_console_endpoint.sh

# ponytail: two terminals required for live UI; build+API alone if you prefer one process
console:
	@echo "Start the API in one terminal:  make console-api"
	@echo "Start the UI in another:        make console-web"
	@echo "Then open http://127.0.0.1:5173"
	@echo "(Or: make console-build && make console-api  →  http://127.0.0.1:8787 )"
	@echo "(Local public bind:             make console-host )"
	@echo "(Nebius https:// URL:           make docker-console IMAGE=… && make nebius-console IMAGE=… SUBNET_ID=… )"

decide: | $(PY)
	@test -n "$(REPORT)" -a -n "$(DECISION)" || { echo 'Usage: make decide REPORT=reports/daily/<date>/<pr folder> DECISION=approve'; exit 1; }
	$(PY) -m reports.pr_report decide "$(REPORT)" "$(DECISION)" --by "$${USER:-reviewer}" --note "$(NOTE)"

test: | $(PY)
	$(VENV)/bin/ruff check .
	$(PY) -m guardrails.no_external .
	$(PY) -m pytest -q
	$(PY) -m evals.run_evals --observations evals/fixtures/golden_v1.jsonl --require-golden --require-v1 --out /tmp/poc-eval-results.json
	@echo ""
	@echo "SELF-CHECK OK"
