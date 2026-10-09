# reports/

- `generate.py` (Nathan): turns an eval result (`python -m evals.run_evals --out ...`) into a Markdown approver
  report: what went right, what went wrong, how to fix it, and an APPROVE / REJECT recommendation.
- `runs/` : one approver report per run (Jonathan's runs and CI runs land here; generated files are not committed
  except samples).
- `samples/`: example reports generated from the dev calibration records.
