# Developer guide

For the plain-language guide see the [README](../README.md); for the PR check and daily run see
[OPERATIONS.md](OPERATIONS.md); for requirements see [REQUIREMENTS.md](REQUIREMENTS.md).

## Layout

| Path | Owner | What |
|---|---|---|
| `Makefile` | Nathan | One-word commands (`make setup`, `make check`, `make daily`, `make test`, ...) |
| `ops/daily_run.py` | Nathan | PR check and daily run: select PRs, test main vs PR, write records and run log |
| `poc/` | Nathan | Verdict enum and rule, deterministic main-vs-PR comparison |
| `reports/` | Nathan (Jonathan's design) | `pr_report.py` (PR runs), `reviewer.py` + `generate.py` (observation records) |
| `harness/` | Jonathan: `br_run.py` (on the box). Nathan: `run.py`, `machine.py` | Downstream-test runner wrapper, shared schema |
| `evals/` | Nathan (golden data: Jonathan) | Checks, golden cases G1-G3, eval CLI, labelled PRs |
| `guardrails/` | Nathan | Schema validation, isolation/timeouts, no-external-side-effects scan |
| `docs/` | both | Requirements, report spec, operations |

## Self-check (what CI runs)

```bash
make test        # = ruff check . ; python -m guardrails.no_external . ; pytest -q ; strict evals
```

Tests never depend on files that exist only on the shared machine: tests that need the golden run artifacts in
`/workspace/blast-radius-research` skip without them (`BR_RESEARCH_DIR` overrides that path; set it to a missing
path to reproduce CI).

## Downstream-test harness (golden records)

```bash
BR_RUNNER=/path/to/br_run.py .venv/bin/python -m harness.run --upstream pandas --old 2.3.3 --new 3.0.0rc0 \
  --dependent UpSetPlot --dep-version 0.9.0 --tests repo:https://github.com/jnothman/UpSetPlot:upsetplot/tests \
  --expected "break: CoW (UpSetPlot #303)" --expected-class break
.venv/bin/python -m evals.run_evals --observations evals/fixtures/golden_v1.jsonl --require-golden --require-v1 --out eval.json
.venv/bin/python -m reports.generate eval.json --out reports/runs/local --claims-dir evals/fixtures/claims
```

Records follow `harness/schema/observation.schema.json` (rev 2; see `harness/schema/README.md`). Report format:
[REPORT_SPEC.md](REPORT_SPEC.md). Samples: `reports/samples/golden-v1/`.

## Workflow

`main` is protected: open a PR from `feat/<topic>`; CI (lint, guardrail, tests, strict evals, reviewer reports on
Python 3.11 and 3.12) must pass; Aritra merges. Nothing in this repo posts, comments or files anything externally.
