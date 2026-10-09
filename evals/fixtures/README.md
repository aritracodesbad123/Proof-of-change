# evals/fixtures

- `observations_ci.jsonl`, used by CI with `--runs-root evals/fixtures --require-golden`:
  - `cal-pandas300rc0-upsetplot090`: Jonathan's dev calibration record (2026-10-10) with `machine_type` and
    `thread_env` **backfilled** (label `fixture-backfill`). Not real harness output.
  - `fixture-raw-sklearn160rc1-imblearn0124`: **constructed by Nathan** from the raw reproduction in
    `/workspace/br-repro`. `per_run` exit/seconds/pytest_summary and JUnit counts are verbatim. The signatures are the
    JUnit first-line messages. `classification` is a hand-set placeholder, because per-category numbers are TODO from Jonathan.
- `runs/fixture-raw-sklearn160rc1-imblearn0124/pytest-new-{1,2,3}.log`: excerpts (first 30 lines + summary line)
  of the raw logs, enough for the `_safe_tags` import-message check.
- Golden cases live in `../golden_cases.json`:
  1. `golden-sklearn160rc1-imblearn-import-failure` (active): old 2238 passed x3; new 0 passed, 525 errors x3;
     `_safe_tags` in the import error. Per-category counts TODO.
  2. `golden-pandas300rc0-upsetplot-cow` (TODO data): exactly 67 real breaks, 6 already broken.
  3. `candidate-clean-pair-sklearn151-152-imblearn` (pending, not golden): 0 breaks once Jonathan confirms.
