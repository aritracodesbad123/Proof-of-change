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

## Daily schedule (IST)

- **10:15** Jonathan updates the registry on the shared machine: `/workspace/blast-radius-research/registry/tracked-libraries.csv`
  (one row per library: `library,repo,added_on_ist,added_by,priority,status,why_added,test_notes`) and, optionally, a
  picks file `registry/picks/<date>.md` naming specific PRs, with install and test commands and an expected verdict.
- **11:15** the ops worker runs `ops/daily_run.py` (equivalent to `make daily`) in the main checkout. The schedule
  lives in the bot's routine, not in this repo (there is no cron file here).

Registry resolution: `--registry`, else `$POC_REGISTRY`, else Jonathan's registry if that path exists, else the
committed seed list `ops/tracked-libraries.csv` (numpy, pandas, scikit-learn).

## Selecting PRs

- **Picks file present for a repo:** exactly those PRs, at the pinned head SHA; selection filters do not apply.
  Expected verdicts are read only after every verdict is final (`read_expectations`), so they cannot steer the run;
  `REPORT.md` then scores expected vs actual (match / miss / false alarm).
- **Otherwise:** open PRs updated since the last run (`ops/seen_prs.json`), not drafts, upstream CI not failing,
  touching Python or compiled code inside the package; pure-Python first; at most `--max-per-library` (3).
- **`--pr <url>`:** exactly that PR (repeatable), no registry, no picks, and `seen_prs.json` cut-offs are not moved,
  so a manual check never changes what the next daily run selects.

## How a PR is tested (routes)

| Route | When | main side | PR side |
|---|---|---|---|
| `nightly+patch` | numpy / pandas / scikit-learn, PR touches only `.py` | latest scientific-python nightly wheel | copy of the main venv with the PR diff applied to the installed package |
| `source-build` | same libraries, PR touches compiled code | nightly wheel | PR head built from source (`--build-timeout`, 1800 s) |
| `source-pair` | any other library | base-branch tip (or merge-base if the PR conflicts) built from git | GitHub's test merge commit (or the PR head) |

Tests: test files mapped from the touched modules (or the picks file's subset), **3 alternating runs per side**
(main 1, PR 1, main 2, ...), `OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1`, pytest `-q -rfE --timeout=120` with JUnit XML,
`--run-timeout` 900 s per run, `-n 4` workers. `GITHUB_TOKEN` (optional, read-only API calls) is removed from the
environment of PR code. The comparison is plain code: `poc/diff.py confirm()` per test over the 3 runs, then
`poc/verdict.py pr_verdict()`.

Verdict: `could_not_verify` if setup/build/patch failed, a run timed out, or no tests ran; `needs_attention` for
regressions, new failing tests, tests missing on the PR side or other outcome changes; `verified` otherwise.

## Files a run writes

```
ops/runs/<folder>/                         (git-ignored)
  REPORT.md            run log for operators: per-PR lines, what went right/wrong, skipped PRs, expected vs actual
  records.jsonl        one record per PR;  selection.json  what was picked and skipped
  <pkg>-<pr>/          record.json, pr.diff, setup-*.log, build-pr.log / patch.log / git.log,
                       pytest-{main,pr}-{1,2,3}.log, junit-{main,pr}-{1,2,3}.xml
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
- **Confidence:** High when every check passes, Medium with warnings, Low for COULD NOT VERIFY.
- **Claims:** C1 is the PR title (not testable until Nemotron claim extraction exists); C2 is the implicit claim
  "tests that pass on main still pass"; one "unmentioned change" row per kind of difference. Each row cites a log
  line: the pytest `FAILED ...` line for a failing test, otherwise the pytest summary line of the relevant side.
  All citations are re-read from disk and must match (`verify`), otherwise the check fails.
- **Evals and guardrails:** 3 runs per side, single-thread env, machine type recorded, nothing posted upstream,
  citations verified (FAIL -> Re-run); flaky tests, PR moved since tested, `pip check` (WARN -> lower confidence).
- **PDF:** headless Chrome/Chromium (`$BR_CHROME`, PATH, or `/Applications/Google Chrome.app`). Without it, HTML and
  Markdown are still written and a note is printed.

## Flags (ops/daily_run.py)

`--pr URL` (repeatable), `--registry`, `--picks`, `--libraries a,b`, `--max-per-library 3`, `--scan-limit 15`,
`--runs 3`, `--workers 4`, `--python 3.12`, `--test-timeout 120`, `--run-timeout 900`, `--build-timeout 1800`,
`--min-free-gb 20`, `--select-only`, `--resume`, `--date`, `--ops-dir`, `--work-dir`, `--report-dir`, `--no-report`.
