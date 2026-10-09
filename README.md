# Blast Radius

Test NumPy, pandas and scikit-learn pre-releases against the projects that depend on them, and find breaking
changes before the release. Every run is checked by evals and guardrails and ends in an approver report
(what went right, what went wrong, how to fix, APPROVE/REJECT).

See `docs/REQUIREMENTS.md`.

## Quick start

```bash
uv venv .venv && uv pip install -p .venv/bin/python -e ".[dev]"
.venv/bin/ruff check . && .venv/bin/pytest -q
.venv/bin/python -m guardrails.no_external .

# one run (needs Jonathan's br_run.py: harness/br_run.py or $BR_RUNNER), uv and git
BR_RUNNER=/path/to/br_run.py .venv/bin/python -m harness.run --upstream pandas --old 2.3.3 --new 3.0.0rc0 \
  --dependent UpSetPlot --dep-version 0.9.0 --tests repo:https://github.com/jnothman/UpSetPlot:upsetplot/tests \
  --expected "break: CoW (UpSetPlot #303)" --expected-class break

# evals + approver report
.venv/bin/python -m evals.run_evals --observations data/observations.jsonl --runs-root data --out eval.json
.venv/bin/python -m reports.generate eval.json -o reports/runs/$(date +%F).md
```

`--legacy` on `run_evals` skips the machine_type/thread_env requirement for records made before the harness existed.

## Layout

| Path | Owner | What |
|---|---|---|
| `harness/` | Jonathan: `br_run.py`, `PROTOCOL.md` (pending). Nathan: `run.py`, `machine.py` | Runner + protocol-enforcing wrapper |
| `evals/` | Nathan (golden data: Jonathan) | Checks, golden cases, eval CLI |
| `guardrails/` | Nathan | Schema, isolation/timeouts, no-external scan |
| `reports/` | Nathan (generator), Jonathan (per-run reports) | Approver reports |
| `docs/` | both | Requirements; research log (Jonathan) |

## Workflow

`main` is protected. Branch `feat/<topic>`, open a PR, CI (lint, guardrails, tests, evals on Python 3.11/3.12) must
pass, Aritra approves and merges. Blast Radius never posts or files anything externally.
