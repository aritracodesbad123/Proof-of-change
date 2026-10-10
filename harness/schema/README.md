# harness/schema

`observation.schema.json` is the single source of truth for observation records (`$id`
`blast-radius/observation/v1`). `guardrails/schema.py` loads it; the runner `br_run.py` validates against it.

Records carry `schema_sha256` (and sometimes `schema_path`, which may name another checkout and is never opened).
Evals accept any revision below, because each revision only adds OPTIONAL fields: a record written against an
earlier revision is still valid under the current file. `schema_version` stays `"1"` for all of them.

| Rev | Date (IST) | sha256 | Change |
|---|---|---|---|
| 1 | 2026-10-10 | `5a3c3d36b7730ce74d0f23b03c88ea862ea35cc327c7d79481fca8b972e8383e` | Initial shared schema (runner v1 + harness fields), `feat/shared-schema` @ `ed75df4` |
| 2 | 2026-10-10 | `088cd395004de286c5f1df76fe94a0dc523738be194166cd3b616c77b6298183` | Optional reviewer-report fields from `docs/REPORT_SPEC.md`: `pr`, `claims`, `upstream_commit_old`, `upstream_commit_new`, `per_test_outcomes`, `old_output`, `golden_check`, `reviewer_decision`. `hand_check` and `upstream_issue` already existed and are unchanged. |
| 3 | 2026-10-10 | `2aafe631c82773d3258d531fb0e07c80ed7823d32fa3f4586d0d9e4a8e8916ca` | Optional record kind `pr_run` (`record_kind`), written by `ops/daily_run.py` for Proof-of-Change PR runs. The v1 `required` list moved unchanged into the `else` branch of `if record_kind == "pr_run"`, so records without `record_kind` validate exactly as before (checked on all 31 records under research/: same result under rev 2 and rev 3). `runs_per_side` minimum 1 moved to the `else` branch (a pr_run whose build failed has 0 runs). Uses `if`/`then`/`else`/`const`. |
| 4 | 2026-10-10 | `0a706f00904fa34ab8ad8bc7f79f53da08dd51576aa2800a3274befb95f7608d` | Optional coverage-gate fields (see `poc/coverage_gate.py`): `changed_lines_total`, `changed_lines_covered` (integer or null = not measured), `coverage` (raw coverage run), `coverage_gate` (kind, changed, confidence, note), `verdict_before_coverage_gate`, `reason_before_coverage_gate`. Nothing becomes required; rev 1-3 records stay valid. |
| 5 | 2026-10-10 | `f6c4e7ba5cd74c5c6259cf3311295a2cc909de20a6802d4b7c4496356c1448ea` | Optional record kind `verification`: an independent checker's verdict on one existing record, in one new optional property `verification` (`checker`, `target`, `verdict_under_review`, `checker_verdict`, `check_status`, `evidence`, optional `mismatch_on`, `counts_reproduced`, `summary`, `later_run_verdict`). There is no top-level verdict, so the checked run's verdict and the checker's verdict cannot be confused; scoring reads only `verification.checker_verdict`. The rev 3/4 `else` branch moved unchanged into a nested `if record_kind == "verification"` / `else`, so observation and pr_run records validate exactly as before. |

Changing the file: bump `x-revisions`, add the new sha256 to this table and to `COMPATIBLE_SCHEMA_SHA256` in
`guardrails/schema.py` (import fails loudly otherwise), and only ever add optional fields within v1. A
breaking change needs `schema_version` "2" and a new `$id`.

## Rev 3 notes for validators

- `required` is no longer a top-level key: observation fields are required under `else`, pr_run fields under `then`.
  A validator that read `SCHEMA["required"]` should read `SCHEMA["else"]["required"]` for observation records.
- Keywords used now: type, required, properties, items, enum, const, pattern, minimum, minLength, if, then, else.
  `ops/schema_check.py` is a stdlib validator for exactly that set (tested against `jsonschema` in tests/).
- `guardrails/schema.py` supports `if`/`then`/`else`/`const` and takes `REQUIRED` from the `else` branch
  (done on `feat/ops-fixes-integrated`).
