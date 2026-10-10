# evals/fixtures

- `golden_v1.jsonl`, used by CI with `--require-golden --require-v1` (strict: full shared v1 schema, every golden case
  required). The three final golden records, copied from the runner's `research/runs/<id>/record.json`
  (runner HARNESS_VERSION 1.0, 10 Oct 2026 IST; machine-local paths and labels replaced with neutral placeholders):
  - `golden-sklearn160rc1-imblearn0124` -> G1 `golden-sklearn160rc1-imblearn-import-failure`
  - `golden-pandas300rc0-upsetplot090` -> G2 `golden-pandas300rc0-upsetplot-cow`
  - `golden-clean-sklearn151to152-imblearn0124` -> G3 `golden-clean-sklearn151-152-imblearn`
  Their `schema_path` names the main checkout (`/data/checkout/harness/schema/...`) because they ran in that
  checkout. That path is never opened; `schema_sha256` is compared with this repo's copy.
  Run logs are not copied (29 MB for G1). With `--runs-root /data/research` the freeze files and
  logs are used as well.
- `observations_ci.jsonl` (pre-v1, kept for unit tests; no longer the CI golden batch):
  - `cal-pandas300rc0-upsetplot090`: the runner's dev calibration record with `machine_type` and `thread_env`
    **backfilled** (label `fixture-backfill`). Not real harness output.
  - `fixture-raw-sklearn160rc1-imblearn0124`: **constructed** from the raw reproduction in
    `/data/repro`. `per_run` and JUnit counts are verbatim. Its `classification` is a placeholder that counts
    all 525 errors as import failures; G1 now rejects it (import failures count once per module: 46).
- `runs/fixture-raw-sklearn160rc1-imblearn0124/pytest-new-{1,2,3}.log`: excerpts of the raw logs, used to test the
  `_safe_tags` import-message check via logs (lines start with pytest's `E   ` prefix; matching ignores it).
- Golden cases live in `../golden_cases.json` (all three `active`).
