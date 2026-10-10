# Proof-of-Change: one-word commands. Type `make` to see them. Details: README.md and docs/OPERATIONS.md.
SHELL := /bin/bash
PYTHON ?= python3
VENV := .venv
PY := $(VENV)/bin/python
export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)

.DEFAULT_GOAL := help
.PHONY: help setup check daily open decide test golden-reports

help:
	@echo "Proof-of-Change commands:"
	@echo "  make setup                              one-time install (creates .venv)"
	@echo "  make check PR=<pull request link>       test one PR and write its report"
	@echo "  make daily                              the daily run over all tracked libraries"
	@echo "  make open                               open the newest report summary"
	@echo "  make decide REPORT=<folder> DECISION=approve|reject|approve_with_notes|re_run [NOTE=\"...\"]"
	@echo "  make test                               self-check: lint, guardrail, tests, evals"

setup:
	@$(PYTHON) -c 'import sys; v=sys.version_info; sys.exit(0 if v >= (3, 11) else "Python " + ".".join(map(str, v[:3])) + " is too old: Proof-of-Change needs Python 3.11 or newer. See README, setup step 2 (Install Python).")'
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
