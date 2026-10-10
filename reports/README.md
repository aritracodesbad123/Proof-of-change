# reports/

Reviewer reports for the human approver (spec: `docs/REPORT_SPEC.md`). Two inputs, one format:

- `pr_report.py`: reports for PR runs written by `ops/daily_run.py` (`make check PR=<url>`, `make daily`). Writes
  `reports/daily/<run folder>/<pr>/REPORT.html|pdf|md` and `SUMMARY.*`; `make decide` records a reviewer decision.
  Details: `docs/OPERATIONS.md`.

- `generate.py`: entry point. `python -m reports.generate <inputs> --out <dir>`; inputs are record.json files,
  observations .jsonl or an eval result .json. Writes `<dir>/<run id>/REPORT.md|html|pdf` and the daily summary
  `<dir>/SUMMARY.md|html|pdf` (needs-attention items first). PDF via headless Chrome/Chromium (`BR_CHROME` to override).
- `reviewer.py`: the report itself (verdict banner, recommended action, confidence, 3-line summary, claims vs reality
  with a cited log line per claim, what changed, what went right, what went wrong + how to fix, trust checks,
  evals and guardrails, checklist, rerun command, evidence links, appendix, glossary). Ported from
  `harness/report/render_report.py` (now a shim).
- `daily/<run folder>/`: PR check and daily run reports (not committed).
- `runs/`: CI and ad-hoc output (not committed).
- `samples/golden-v1/`: committed samples for the three golden records, generated with
  `--runs-root <research dir> --claims-dir evals/fixtures/claims --require-v1`. Their links point at
  the run artifacts under the research folder (relative paths, valid only where those artifacts exist).
