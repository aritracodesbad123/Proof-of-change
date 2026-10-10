# Operations: the PR check and the daily run (technical)

Plain-language version: the [README](../README.md). This page is the detail behind it.

## Entry points

| Command | Runs | Output |
|---|---|---|
| `make check PR=<url>` | `ops/daily_run.py --pr <url>` | `ops/runs/<date>-check-<HHMM>/`, `reports/daily/<date>-check-<HHMM>/` |
| `make daily` | `ops/daily_run.py` | `ops/runs/<date>/`, `reports/daily/<date>/` |
| `make decide REPORT=<dir> DECISION=<d>` | `python -m reports.pr_report decide` | `<dir>/DECISION.json`, report re-rendered |
| `python -m reports.pr_report <ops run dir> --out <dir>` | re-render reports from an existing run | `<dir>/<pr>/REPORT.*`, `<dir>/SUMMARY.*` |

`make` puts `.venv/bin` first on `PATH`, so the `uv` installed by `make setup` (extra `ops`) is the one the runner uses.

## Inputs of a daily run

- **Tracked libraries:** a CSV, one row per library: `library,repo,added_on_ist,added_by,priority,status,why_added,
  test_notes`. Resolution: `--libraries-file`, else `$POC_LIBRARIES_FILE`, else `libraries_file` in `ops/local.json`,
  else the committed seed list `ops/tracked-libraries.csv` (numpy, pandas, scikit-learn).
- **Chosen PRs (optional):** a `<date>.md` file naming specific PRs per library, with install and test commands and
  an expected verdict. Resolution: `--chosen-prs`, else `<chosen_prs_dir>/<date>.md` (`$POC_CHOSEN_PRS_DIR` or
  `ops/local.json`), else `<libraries file folder>/chosen-prs/<date>.md`.
- **Independent verification (optional):** `<verification_dir>/<date>/verification.jsonl` (or, if present, a
  `verification*.jsonl` file of schema-rev-5 `verification` records), scored after all verdicts. For rev-5 records
  only `verification.checker_verdict` is scored; `verdict_under_review` (the checked run's own verdict) never is, and
  records with `check_status` `unverified` are skipped.

`ops/local.json` is git-ignored and holds machine-local paths (keys: `libraries_file`, `chosen_prs_dir`,
`verification_dir`, `golden_status`, `research_dir`; see `poc/local_config.py`). Environment variables override it.
There is no scheduler in this repo; run `make daily` (or `ops/daily_run.py`) from whatever scheduler you use.

## Selecting PRs

- **Chosen-PRs file names PRs for a repo:** exactly those PRs, at the pinned head SHA; selection filters do not apply.
  Expected verdicts are read only after every verdict is final (`read_expectations`), so they cannot steer the run;
  `REPORT.md` then scores expected vs actual (match / miss / false alarm).
- **Otherwise:** open PRs updated since the last run (`ops/seen_prs.json`), not drafts, upstream CI not failing,
  touching Python or compiled code inside the package; pure-Python first; at most `--max-per-library` (3).
- **`--pr <url>`:** exactly that PR (repeatable), no library list, no chosen-PRs file, and `seen_prs.json` cut-offs are not moved,
  so a manual check never changes what the next daily run selects.

## How a PR is tested (routes)

| Route | When | main side | PR side |
|---|---|---|---|
| `nightly+patch` | numpy / pandas / scikit-learn, PR touches only `.py` | latest scientific-python nightly wheel | copy of the main venv with the PR diff applied to the installed package |
| `source-build` | same libraries, PR touches compiled code | nightly wheel | PR head built from source (`--build-timeout`, 1800 s) |
| `source-pair` | any other library | base-branch tip (or merge-base if the PR conflicts) built from git | GitHub's test merge commit (or the PR head) |

Tests: test files mapped from the touched modules (or the chosen-PRs file's subset), **3 alternating runs per side**
(main 1, PR 1, main 2, ...), `OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1`, pytest `-q -rfE --timeout=120` with JUnit XML,
`--run-timeout` 900 s per run, `-n 4` workers. PR code never sees our environment (see "Environment of untrusted
code" below). The comparison is plain code: `poc/diff.py confirm()` per test over the 3 runs, then
`poc/verdict.py pr_verdict()`.

Both sides get the library's test extras plus `optional_test_deps` (per library in `LIBS`), so tests don't skip
for missing optional modules. The nightly wheel is pinned (exact file, sha256, build date and commit are recorded);
source-pair records the GitHub test merge commit. Thread env: `OMP`, `OPENBLAS`, `MKL`, `NUMEXPR`, `VECLIB_MAXIMUM`,
`BLIS` thread counts all 1.

Comparison: rename-aware. An id that disappears is only `removed_tests` if no new id with the same base test name
appeared; otherwise it is listed under `reparametrized` and the new ids are judged by their own outcomes. Failures
identical on both sides are `preexisting_failures`. Unexplained pytest exit codes give `could_not_verify`.

Test modules that fail to load (collection errors: JUnit testcases with an empty classname) are tracked as modules,
never as tests: their ids are made side-independent on every route (the environment / `site-packages.` prefix is
dropped), and they are listed as `load_failed_both`, `load_failed_pr` (with the number of main-side tests that no
longer run) or `load_failed_main`. They never count as "unchanged", removed or new. `executed` records the fewest tests
that actually ran (passed, failed or errored; not skipped, not load failures) in any run of each side.

Verdict, in order:

1. `could_not_verify` if setup/build/patch failed, a run timed out or a side produced no results;
2. `needs_attention` for regressions or new failing tests (nothing below can hide them);
3. `could_not_verify` if no test actually ran on a side (every test skipped, or every module failed to load);
4. `could_not_verify` if a test module loads on one side only ("test module X fails to load on the PR side (N
   test(s) no longer run)");
5. `could_not_verify` if a test module of the changed code (`test_<stem>.py` of a changed source file, or a changed
   test file; every module when the changed files are unknown) fails to load on both sides, even if unrelated tests
   pass;
6. `could_not_verify` if an exit code is unexplained, or new/changed tests were skipped because an optional
   dependency is missing;
7. otherwise `needs_attention` for tests missing on the PR side or other outcome changes, `verified` if nothing differs.

Then the coverage gate. The reason says how many tests ran on each side, how many were unchanged (and how many of
those were skipped on both sides), flaky tests, and every module that failed to load.

## Coverage gate (`poc/coverage_gate.py`)

"Verified" must mean the changed code was exercised. After the 3 timed runs, `coverage_run()` installs `coverage` and
`pytest-cov` into the PR venv and runs the PR side's test subset once more under `--cov=<dirs of the changed
files>` (untimed, so the 3 timed runs stay clean; logs `coverage-pytest.log`, data `coverage-pr.json`). Changed lines
are computed by `difflib` between the main-side file and the PR-side file that was actually tested (exact for every
route, including a diff applied with offsets); executable lines are coverage.py's executed + missing lines. Only
non-test Python files that ship with the library count (not `tests/`, `test_*.py`, `conftest.py`, docs, benchmarks,
`setup.py`).

| Case | Effect |
|---|---|
| Python changes, 0% of changed executable lines ran | `verified` -> `could_not_verify`, reason "not fully verified: changed code never ran: 0 of N ..." |
| Python changes, under 50% | verdict kept; `coverage_gate.confidence = lower` (report: WARN, Medium confidence) |
| Python changes, coverage not measured (old record, `--no-coverage`, or the coverage run failed) | verdict kept; confidence lower; note says why |
| Compiled sources (`.c .h .cpp .pyx .pxd ...`, not build config) and no changed test file whose name contains the module stem | `verified` -> `could_not_verify`, "not fully verified: compiled code changed (...)" |
| No executable change (docs/tests/config) | stays `verified`, note "no executable code changed" |
| `needs_attention` / `could_not_verify` | never changed |

Record fields (schema rev 4, all optional): `changed_lines_total`, `changed_lines_covered` (null = not measured),
`coverage` (raw run), `coverage_gate` {kind, changed, confidence, note}, `verdict_before_coverage_gate`,
`reason_before_coverage_gate`. The gate is idempotent. Records are gated before they are written, so
`records.jsonl`, each `record.json` and `REPORT.md` state the same final verdict; `reports/pr_report.py` re-applies
the gate when rendering.

**Limitations.** coverage.py cannot measure compiled code, so the compiled rule is a heuristic: a changed test file
named after the module (`item_selection.c` -> `test_item_selection.py`) counts as "a test that calls into the changed
module"; it does not prove the test reaches the changed C lines, and a test with an unrelated name is not recognised.
A PR mixing Python and compiled changes gets both rules. Lines run only by import (module-level code) count as
covered. The coverage run adds roughly one more test run per PR (about 15-60 s on day-1 PRs).

## Environment of untrusted code (`guardrails/isolation.py`)

Every subprocess that may run code from a PR or a package gets an **allowlisted** environment built by
`untrusted_env()`, never a filtered copy of ours. That covers installs and builds of either side, pytest, the coverage
run, probes, `uv pip freeze`, `patch` and every start of a venv Python (installed `.pth` files run on startup). It
applies to `make check` and the daily run (`ops/daily_run.py`, `base_env()`), and to the release-pair runner
started by `harness/run.py`.

| Variable | Value |
|---|---|
| `PATH`, `LANG`, `LC_ALL`, `TERM`, `TMPDIR`, `SOURCE_DATE_EPOCH`, `SSL_CERT_FILE` | passed through, only if set |
| `HOME` | a per-environment temporary home (`work/home-main`, `work/home-pr`, `work/home-git`), never the real one |
| `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `BLIS_NUM_THREADS` | `1` |
| `PYTHONHASHSEED` / `PYTHONDONTWRITEBYTECODE` / `MPLBACKEND` | `0` / `1` / `Agg` |
| installs only: `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR` | the real uv cache and managed-Python dirs (so a temporary HOME does not re-download everything) |
| installs only: `UV_LINK_MODE` / `UV_NO_CONFIG` | `copy` (installed files never share inodes with the cache) / `1` (no uv config files) |
| installs only, per call: `SETUPTOOLS_SCM_PRETEND_VERSION` | `9999.0.0` for checkouts without tags |

Everything else is dropped: tokens, API keys, database URLs, proxies, `PIP_*`/`UV_INDEX_*`, `PYTHONPATH`, `CI`,
`DISPLAY`, `XDG_*`. A second, independent check (`SECRET_NAME`: TOKEN, SECRET, PASSWORD, KEY, AUTH, PAT, DSN,
DATABASE_URL, COOKIE, SESSION, ...) fails loudly at import time if a credential-looking name is ever added to the
allowlist, and again on every environment built (also for values that are URLs with a password). `run()` refuses
to start anything without an explicit environment. Proxies are not passed through: on a machine that needs one,
installs fail visibly instead of handing proxy credentials to PR code. The temporary HOME hides files such as
`~/.netrc` and `~/.git-credentials` by default. It is not a filesystem sandbox: code can still read absolute paths
the user can read.

## Probes (`poc/probes.py`, `probes/`)

Tests only show what the test suite checks. A **probe** checks one specific behaviour of a PR directly: a small,
deterministic Python script that runs on both sides (main and PR) in the same isolated environments the tests used,
prints observations as JSON, and plain code compares them. Only fixed probes exist today, one file per PR under
`probes/<owner>/<repo>/<pr>.py` (more than one: `<pr>-<name>.py`). Model-written probes will use the same interface.

Interface. The file starts with a literal `PROBE` dict (read with `ast.literal_eval`, never imported):
`id`, `target` (`owner/repo#pr`), `about`, `timeout_s` (optional, default 120 s), and `claims`: what the PR says,
each `{id, text, source, covers: [glob patterns over observation names], expect: "same" | "differs"}`. Its last
stdout line is `{"observations": {"<name>": <JSON value>, ...}}`. Each side runs 3 times, alternating, with that
side's venv Python, an empty working directory and that side's allowlisted environment (see above; same as the
tests). Each run's observations are saved one per line as `probe-<id>-<side>-<n>.jsonl` (plus a `.log`
with the full output), and every observation in the record cites its line in run 1 of each side.

Labels, per observation:

| Observation | Claim covering it | Label | Verdict effect |
|---|---|---|---|
| same on both sides | expects same | `proven` | none |
| same on both sides | none | `no_difference` | none |
| same on both sides | expects differs | `needs_human` | needs_attention |
| differs | expects differs | `proven` | none |
| differs | expects same | `false_claim` | needs_attention |
| differs | none | `unmentioned` | needs_attention |
| varies between runs of one side | any | `flaky` | needs_attention |
| probe crashed on both sides | - | `not_testable` | none (reported) |

A probe that crashes on one side only shows up as the `probe.error` observation differing (`unmentioned`).

Verdict rule. The tests decide first (comparison, then the rules above); then any probe observation needing
attention makes the verdict needs_attention, also over could_not_verify, because a difference was actually seen.
Green probes never upgrade a verdict. The coverage gate runs after this and never lowers needs_attention. A PR
without a probe file gets exactly the tests' verdict and reason; its record says `"probes": {"status": "none"}`.
The record (schema rev 6, additive) keeps every run's observations, so `--rejudge` recomputes the labels without
environments. The reviewer report has a **Probes** section (each observation with both values and its citations)
and adds the claims as rows `P-C1`, ... in the claims table; observations no claim covers are listed as
"Change not in the PR description". The golden known-answer case `golden-pr-mlxtend-1229-probe`
(`evals/fixtures/golden_pr_v1.jsonl`) is part of `--require-golden`: tests alone pass on that PR (verified), the
probe finds two unclaimed behaviour changes, so the expected verdict is needs_attention.

## Files a run writes

```
ops/runs/<folder>/                         (git-ignored)
  REPORT.md            run log for operators: per-PR lines, what went right/wrong, skipped PRs, expected vs actual
  records.jsonl        one record per PR;  selection.json  what was picked and skipped
  run_meta.json        timings, machine, problems (needed by --report-only)
  superseded/attempt-N/ earlier attempts of the same date (records, logs, NOTE.md); the selection stays frozen
  <pkg>-<pr>/          record.json, pr.diff, setup-*.log, build-pr.log / patch.log / git.log, freeze-{main,pr}.txt,
                       pytest-{main,pr}-{1,2,3}.log, junit-{main,pr}-{1,2,3}.xml,
                       coverage-pytest.log, coverage-pr.json (coverage gate)
ops/work/                                  scratch venvs and checkouts, deleted after each PR (git-ignored)
ops/seen_prs.json                          incremental state for the daily selection (git-ignored)
reports/daily/<folder>/                    (git-ignored)
  SUMMARY.html|pdf|md  needs-attention first
  <pkg>-<pr>/REPORT.html|pdf|md, SOURCE.json (where it came from), DECISION.json (after make decide)
```

## The reviewer report for a PR run (`reports/pr_report.py`)

Same section order, renderers and verdict vocabulary as the golden-record reports (`reports/reviewer.py`,
[REPORT_SPEC.md](REPORT_SPEC.md)), adapted to main-vs-PR:

- **Verdict mapping:** `verified` -> VERIFIED / Approve (Approve with notes if a check warned or tests were fixed);
  `needs_attention` -> NEEDS ATTENTION / Reject; `could_not_verify` -> COULD NOT VERIFY / Re-run. **Any failed
  check below also gives COULD NOT VERIFY / Re-run** (the run cannot be trusted).
- **Coverage gate:** a gated `could_not_verify` (reason "not fully verified ...") is COULD NOT VERIFY / **Review by
  hand** (a re-run would not change it), Low confidence. Low coverage or "not measured" is a WARN. The summary lists
  every verdict the gate changed under "Changed by the coverage gate", and earlier attempts under "Re-runs".
- **Record shape:** pr_run records (schema rev 3+) keep the PR in a `pr` object and durations in `duration_s`;
  `normalize()` flattens them (older flat records still render).
- **Confidence:** High when every check passes, Medium with warnings, Low for COULD NOT VERIFY.
- **Claims:** C1 is the PR title (not testable until Nemotron claim extraction exists); C2 is the implicit claim
  "tests that pass on main still pass"; one "unmentioned change" row per kind of difference. Each row cites a log
  line: the pytest `FAILED ...` line for a failing test, otherwise the pytest summary line of the relevant side.
  All citations are re-read from disk and must match (`verify`), otherwise the check fails.
- **Evals and guardrails:** 3 runs per side, single-thread env, machine type recorded, nothing posted upstream,
  citations verified (FAIL -> Re-run); flaky tests, PR moved since tested, `pip check` (WARN -> lower confidence).
- **Known-answer replay (ported from render_report.py):** if the latest replay status file (`$BR_GOLDEN_STATUS`,
  else `golden_status` in `ops/local.json`; JSON with `all_passed`, `date_ist`, `failed`) has
  `all_passed: false`, every report is COULD NOT VERIFY / Re-run with Low confidence. The same applies to the
  golden-record reports (`reports/reviewer.py`), where a record's own failed `golden_check` also forces it. Tests set
  `BR_GOLDEN_STATUS` to empty so they never depend on a machine-local file.
- **PDF:** headless Chrome/Chromium (`$BR_CHROME`, PATH, or `/Applications/Google Chrome.app`). Without it, HTML and
  Markdown are still written and a note is printed.

## Flags (ops/daily_run.py)

`--pr URL` (repeatable), `--libraries-file`, `--chosen-prs`, `--verification`, `--libraries a,b`, `--max-per-library 3`,
`--scan-limit 15`, `--runs 3`, `--workers 4`, `--python 3.12`, `--test-timeout 120`, `--run-timeout 900`,
`--build-timeout 1800`, `--min-free-gb 20`, `--select-only`, `--resume`, `--reselect`, `--rerun-note TEXT`,
`--report-only` (rebuild REPORT.md and the reviewer reports from `records.jsonl`, `run_meta.json` and
`selection.json`; nothing is re-tested. Saved records are first brought up to the current rules: a calendar date in
`run_date` and the gated final verdict. Changed `records.jsonl` / `record.json` files are rewritten and the originals
kept once under `pre-migration/`), `--rejudge` (with `--report-only`: also recompute each verdict from the saved
JUnit files with the current comparison rules; the previous verdict is kept under `rejudged`), `--date` (run folder,
may be nested, e.g. `<date>/<name>`; `run_date` is the folder's calendar date), `--ops-dir`, `--work-dir`, `--report-dir`, `--no-report`,
`--no-coverage` (skip the coverage run; the gate then says "not measured"), `--no-probes` (do not run probe files;
the record says `"probes": {"status": "none"}`).

A full daily run takes about 15-20 minutes (day 1: 15 PRs in 16.4 min wall time, before the coverage run existed).
