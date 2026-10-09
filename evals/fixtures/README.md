# evals/fixtures

- `observations_ci.jsonl`: Jonathan's two dev calibration records (2026-10-10) with `machine_type` and
  `thread_env` **backfilled** (label `fixture-backfill`) so CI can run the strict evals. Not real harness output.
- Golden cases live in `../golden_cases.json`. All three are `status: TODO` until Jonathan delivers the final data:
  1. `golden-sklearn160rc1-imblearn-import-failure`: import must fail (import_failure >= 1); exact counts TODO.
  2. `golden-pandas300rc0-upsetplot-cow`: exactly 67 real breaks, 6 already broken.
  3. `golden-clean-pair-zero-breaks`: pair TODO; must show 0 breaks.
