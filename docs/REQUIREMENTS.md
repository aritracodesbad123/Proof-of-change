# Blast Radius: requirements

Status: draft v0.2 (2026-10-10; v0.2 applies Jonathan's golden-case update), by Nathan (ops/QA/dev). Awaiting review by Aritra and Jonathan.
Sources: Jonathan's runner (`br_run.py`), his two dev calibration records (`research/dev-runs/observations-dev.jsonl`,
2026-10-10), the reproductions in `/workspace/br-repro`, and the project plan
(`nvidia-nebius-hackathon/blast-radius-pydata-plan.md`). Items marked **[ASSUMED]** are not stated in those sources
and need confirmation; see section 13.

## 1. Goal

Before a NumPy, pandas or scikit-learn release, install the old and the new (pre-release) upstream version side by
side, run the test suites of projects that depend on it against both, and report which dependents break, so the
breaks can be raised before the final release. Example: pandas 3.0.0rc0 broke 67 UpSetPlot tests 49 days before the
3.0.0 final; the user report (UpSetPlot issue #303) came 4 days after the final.

## 2. Scope

In scope (v1):
- Upstreams: NumPy, pandas, scikit-learn. Pre-releases from PyPI (`rc`, `b`) and the scientific-python nightly index.
- Dependents: the 18 targets in the plan (section 2.2) plus reserves; tests from the wheel or from the repo at the
  matching release tag.
- Per tuple (upstream, old, new, dependent): two isolated environments that differ only in the upstream, 3 alternating
  runs per side, per-test classification, one observation record, one approver report.
- Evals and guardrails enforced on every run, including runs submitted by Jonathan.
- Later: Nemotron explanations of real breaks, with log-line citations.

Out of scope:
- Filing issues, commenting, posting or emailing anywhere. A person decides what to send upstream.
- Rebuilding dependents from source (it would hide ABI breaks like NumPy 2.0).
- The Nebius executor until credentials exist (`--executor nebius` currently exits with an error).

## 3. Roles

| Who | Role | Owns |
|---|---|---|
| Aritra Chakraborty | Approver and repo owner | Approves or rejects each run from its approver report; merges to `main`. |
| Jonathan | Baseline and protocol owner | `harness/br_run.py`, `harness/PROTOCOL.md`, golden eval data, per-run reports, research log; sends 3 libraries a day. |
| Nathan | Ops, QA, dev; eval and guardrail enforcer | Harness wrapper, `evals/`, `guardrails/`, report generator, CI/CD, routine checks. Enforces evals and guardrails on every record, Jonathan's included. |

## 4. Functional requirements

- FR1. The runner builds the OLD env with `upstream==old` and the dependent resolved; the NEW env is the OLD freeze
  with only the upstream swapped (`--no-deps`). `env_diff` must contain exactly the two upstream pins.
- FR2. Tests run 3 times per side, alternating old, new, old, new, old, new.
- FR3. Every run uses `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=1`, `MPLBACKEND=Agg`,
  no `PYTHONPATH`, and pytest-xdist with a fixed worker count (default 4).
- FR4. Per-test timeout (default 120 s) and per-invocation timeout (default 1200 s); a timeout kills the whole process
  group and is recorded as `exit: "timeout"`.
- FR5. Each test is classified as one of `real_break`, `already_broken`, `flaky`, `import_failure`, `fixed_by_new`,
  `lost_tests` (logic in `br_run.py::classify`). Error messages are grouped into signatures.
- FR6. The expected outcome (`expected`, `expected_class`) is written before the run and compared afterwards.
- FR7. Each record names the machine type it ran on (Jonathan's constraint), including the GitHub runner in CI.
- FR8. Each run produces an approver report (section 9) that ends with APPROVE or REJECT.
- FR9. Run artifacts (freeze files, JUnit XML, pytest logs, class lists) are kept under `runs/<id>/` so every
  number and every LLM claim can be traced to a file and line.
- FR10. Later: Nemotron explains each real-break group. Each claim must cite at least one log line (section 7, E6).

## 5. Record schema

One JSON object per line in `observations.jsonl`, also written to `runs/<id>/record.json`. Fields 1 to 37 are written
by `br_run.py` today (verified against both dev records); 38 and 39 are added by `harness/run.py`. Enforced by
`guardrails/schema.py`.

| Field | Type | Notes |
|---|---|---|
| id | str | e.g. `cal-pandas300rc0-upsetplot090` |
| date_ist | str | `YYYY-MM-DD HH:MM IST` |
| who | str | e.g. `Jonathan (box)` |
| upstream, old_version, new_version, new_version_requested | str | installed vs requested new version |
| new_direct_url | str/null | set for nightly or git installs |
| dependent, dependent_version, test_source, test_selection | str | |
| subset_note | str/null | why a subset was chosen |
| python, machine, host, platform | str | `machine` is a free label (`box`, `nebius`) |
| cpu_count | int | |
| runs_per_side | int | must be 3 |
| workers | str | xdist workers |
| test_timeout_s, run_timeout_s | int | |
| env_diff | list[str] | must be exactly `[upstream==old, upstream==new]` |
| pip_check_new | str | `ok` or the conflict text |
| per_run | list | each: side, run, exit (int or `"timeout"`), seconds, passed, failed, error, collection_errors, skipped, pytest_summary |
| classification | dict | the six class counts, non-negative ints |
| top_error_signatures_breaks, top_error_signatures_already_broken | list[[str, int]] | |
| duration_s | dict | total_wall, tests_old_mean, tests_new_mean |
| expected, expected_class, matches_expected | str | class in no_break/break/unknown; match in yes/no/n/a |
| hand_check, upstream_issue, notes | str/null | |
| logs | str | path of `runs/<id>/` relative to the data root |
| **machine_type** (new) | dict | arch, os, platform, cpu_count, ci, runner_name, runner_os, runner_arch, runner_environment, image, label |
| **thread_env** (new) | dict | the single-thread variables used, all `"1"` |
| explanations (future) | list | Nemotron claims: `{text, citations: [{file, line, quote}]}` |

## 6. Golden eval cases (from Jonathan)

Stored in `evals/golden_cases.json`. Statuses:
- `active`: hard gate. If the pair is in a batch and misses any expected value, the run is REJECTED. In a golden batch
  (`--require-golden`, used by CI) a missing active case also fails.
- `TODO`: values agreed, final pinned data still to come. Enforced when the pair is present; never required.
- `pending`: candidate only, not golden. Mismatches are WARN, never FAIL.

Per-run counts are read from pytest's own summary line (`per_run[].pytest_summary`), because the JUnit-derived
`per_run[].passed` counts xpassed tests as passed (e.g. 2243 = 2238 passed + 5 xpassed).

| Case | Status | Pair | Expected |
|---|---|---|---|
| G1 `golden-sklearn160rc1-imblearn-import-failure` | active | scikit-learn 1.5.2 -> 1.6.0rc1 vs imbalanced-learn 0.12.4 | Gated on the raw reproduction (`/workspace/br-repro`): every old run `2238 passed`; every new run `0 passed` and `525 errors` (all 525 test modules fail to load), 3 runs per side; the new-side import failure message contains `_safe_tags` (E5b); prediction matches. Per-category classification counts: **TODO** (Jonathan; the dev-run 280 real_break / 1,713 lost_tests were a runner miscount and are dropped). |
| G2 `golden-pandas300rc0-upsetplot-cow` | TODO | pandas 2.3.3 -> 3.0.0rc0 vs UpSetPlot 0.9.0 | exactly 67 real_break, 6 already_broken, 0 import_failure; top signatures include `Invalid RGBA argument: nan` |
| C1 `candidate-clean-pair-sklearn151-152-imblearn` | pending, **not golden** | scikit-learn 1.5.1 -> 1.5.2 vs imbalanced-learn | 0 real_break, 0 import_failure, 0 lost_tests. Becomes golden only after Jonathan confirms zero breaks over 3 runs per side; pins TODO. |

## 7. Evals (enforced on every record: `python -m evals.run_evals`)

| Id | Check | FAIL when | 
|---|---|---|
| E1 | schema | any field missing or mistyped; `machine_type`/`thread_env` missing (strict mode) |
| E2 | versions_installed | new version != requested; `env_diff` has anything other than the upstream pins; freeze files disagree. WARN if `pip check` on the new env reports conflicts |
| E3 | runs_per_side | not exactly 3 runs per side, not alternating, or any run timed out. WARN if counts vary within a side |
| E4 | single_thread | `thread_env` present with a value other than 1. WARN if not recorded |
| E5 | golden cases | an active/TODO golden pair is in the batch and misses its expected values (class counts, per-run pytest summary counts, signatures). Pending candidates only WARN |
| E5b | golden import message | G1 is in the batch and no new-side import error mentions `_safe_tags`. Sources in order: record `import_failure_messages` (planned runner field), break signatures, then `runs/<id>/pytest-new-N.log` (must hit in every new run). SKIP if none is available |
| E6 | llm_citations | any Nemotron claim has no citation, cites a file outside `runs/<id>/`, a missing line, or a line that does not contain the quoted text |
| E7 | matches_expected | WARN only: a mismatch is either a finding or a wrong prediction; the approver decides |
| E8 | golden coverage | golden batch only (`--require-golden`, CI): an active case is absent. Daily batches: SKIP |

## 8. Guardrails

- G-ext: no external side effects. `guardrails/no_external.py` scans code and workflows for `gh issue/pr/api`,
  `git push`, HTTP POST/PUT/PATCH/DELETE, smtplib, GitHub write endpoints and Slack posts; CI fails on any hit.
  CI uses a read-only `GITHUB_TOKEN` (`permissions: contents: read`). Exceptions need a reviewed
  `# br-allow-external:` marker.
- G-iso: each side has its own venv inside `runs/<id>/`; `PYTHONPATH` removed; tests run from an empty `work/` dir;
  each pytest call runs in its own process group with a timeout (`guardrails/isolation.py`).
- G-schema: every record, from anyone, is schema-validated before it is accepted (`harness/run.py` and E1).
- G-protocol: `harness/run.py` refuses `--runs` other than 3 and forces the single-thread variables.

## 9. Approver report

Generated by `python -m reports.generate <eval.json> -o reports/runs/<batch>.md`, one per run or batch. Contents:
header (source, evaluating machine, schema mode), overall **APPROVE/REJECT**, per-run table, golden coverage; then per
run: pair, who/when, machine type, tests, prediction, class counts, top break signatures, **What went right** (passed
checks), **What went wrong** (FAIL/WARN with details), **How to fix** (one action per problem), and pending items.
Rule: any FAIL means REJECT; WARN and TODO are shown but do not block. Sample:
`reports/samples/approver-report-dev-calibration-2026-10-10.md`.

## 10. CI/CD

- Repo `aritracodesbad123/blast-radius` (to be created). `main` protected: PR required, CI must pass, no force push.
- Work on `feat/*` branches, opened as PRs into `main`. Aritra approves and merges.
- `.github/workflows/ci.yml` on push to `main`/`feat/**` and on PRs: matrix Python 3.11 and 3.12 on `ubuntu-latest`,
  single-thread env; records the runner machine type (JSON + step summary); ruff; no-external guardrail; pytest; strict
  evals with `--require-golden` on `evals/fixtures/observations_ci.jsonl` (G2 dev record + a G1 record built from the raw reproduction, with log excerpts); approver report to the step summary and as an artifact.
- Heavy suites (real dependent runs) are not in PR CI **[ASSUMED]**; they run on the box or a scheduled/Nebius job and
  their records go through the same evals.

## 11. Daily cadence

- From Sunday 2026-10-11, 10:15 AM IST, Jonathan sends 3 libraries a day to test using `harness/PROTOCOL.md`.
- Nathan runs each through `python -m harness.run`, then `evals.run_evals` + `reports.generate`, and posts the
  approver report for Aritra the same day **[ASSUMED: same-day turnaround]**.
- Records Jonathan submits from his own runs go through the same evals before they are counted.

## 12. Repository layout

```
docs/REQUIREMENTS.md        this document (research log: reserved for Jonathan)
harness/                    br_run.py + PROTOCOL.md (Jonathan, pending); run.py, machine.py (Nathan)
evals/                      checks, golden_cases.json, run_evals.py, fixtures/
guardrails/                 schema, isolation/timeouts, no-external scan
reports/                    generate.py; runs/ (per-run reports); samples/
tests/                      pytest
.github/workflows/ci.yml
```

## 13. Open questions and assumptions

1. ~~G1 exact numbers~~ **Resolved (v0.2):** G1 gates on the raw reproduction (2238 passed old; 0 passed and 525
   errors new, x3; `_safe_tags`). The dev-run numbers were a runner miscount and are dropped. Per-category counts
   remain TODO from Jonathan.
2. ~~G3 clean pair~~ **Resolved (v0.2):** candidate scikit-learn 1.5.1 vs 1.5.2 on imbalanced-learn, `pending` until
   Jonathan confirms zero breaks over 3 runs per side.
3. G2 environment: confirm pins (numpy 2.3.5, matplotlib 3.10.8, pytest 9.1.1, Python 3.13).
4. CI matrix is 3.11/3.12 as requested, but the calibration runs used Python 3.13.5. Should real runs pin 3.13? **[ASSUMED: CI matrix only tests our tooling; runs keep the runner's `--python 3.13`.]**
5. **Decided:** Jonathan is adding `machine_type` and `thread_env` to `br_run.py`; strict E1 stays on. Until his
   runner writes them, records from direct `br_run.py` calls fail E1 (records via `harness/run.py` pass).
6. Workers: records use `workers: "4"`. Does "single-thread" also mean `--workers 0`? **[ASSUMED: no; single-thread
   applies to BLAS/OpenMP inside each worker.]**
7. Is a matches_expected mismatch WARN (current) or FAIL?
8. Where are approver reports delivered (group chat, PR comment, file only)? PR comments would need a reviewed
   exception to G-ext.
9. Nemotron: model/endpoint, and the exact claim/citation format (draft in section 5).
10. Per-day reporting deadline and who approves when Aritra is away.
11. Schema convergence: Jonathan's new runner writes schema v1 (`harness/schema/observation.schema.json`: adds
    `schema_version`, `gates`, `accepted`, `network`, `report`, `explanation`, `stability`, ...; drops `hand_check`
    and `upstream_issue`). `guardrails/schema.py` must be aligned to it (one shared schema file) once it settles.
12. G1 dev run vs raw reproduction: the dev run's pytest summary itself reads `280 failed, 250 passed, 13 errors`, so the
    difference from the raw `525 errors` is in how tests were run (likely `--import-mode=importlib`/`-P`, 4 vs 8
    workers), not only in counting. Jonathan to confirm the runner reproduces `525 errors` before G1 can pass on a
    runner record. Old side also differs by one test (2239 vs 2238 passed, 32 vs 33 skipped).
13. Runner should record import-failure messages (`import_failure_messages`); JUnit only says `collection failure`.
