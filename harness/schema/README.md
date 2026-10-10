# harness/schema

`observation.schema.json` is the single source of truth for observation records (`$id`
`blast-radius/observation/v1`). `guardrails/schema.py` loads it; Jonathan's `br_run.py` validates against it.

Records carry `schema_sha256` (and sometimes `schema_path`, which may name another checkout and is never opened).
Evals accept any revision below, because each revision only adds OPTIONAL fields: a record written against an
earlier revision is still valid under the current file. `schema_version` stays `"1"` for all of them.

| Rev | Date (IST) | sha256 | Change |
|---|---|---|---|
| 1 | 2026-10-10 | `5a3c3d36b7730ce74d0f23b03c88ea862ea35cc327c7d79481fca8b972e8383e` | Initial shared schema (Jonathan v1 + Nathan fields), `feat/shared-schema` @ `ed75df4` |
| 2 | 2026-10-10 | `088cd395004de286c5f1df76fe94a0dc523738be194166cd3b616c77b6298183` | Optional reviewer-report fields from `docs/REPORT_SPEC.md`: `pr`, `claims`, `upstream_commit_old`, `upstream_commit_new`, `per_test_outcomes`, `old_output`, `golden_check`, `reviewer_decision`. `hand_check` and `upstream_issue` already existed and are unchanged. |

Changing the file: bump `x-revisions`, add the new sha256 to this table and to `COMPATIBLE_SCHEMA_SHA256` in
`guardrails/schema.py` (import fails loudly otherwise), and only ever add optional fields within v1. A
breaking change needs `schema_version` "2" and a new `$id`.
