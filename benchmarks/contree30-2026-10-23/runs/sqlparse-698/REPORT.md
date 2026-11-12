# Proof-of-Change daily ops run: sqlparse-698

Started 2026-10-24 09:34 IST, finished 2026-10-24 11:07 IST, wall time 92.6 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [andialbrecht/sqlparse#698](https://github.com/andialbrecht/sqlparse/pull/698) | feat(databricks): add initial databricks syntax | source-pair | **could_not_verify** | Contree could not prepare the main and PR sides (contree request failed: ApiTimeoutError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- andialbrecht/sqlparse#698: could not verify: Contree could not prepare the main and PR sides (contree request failed: ApiTimeoutError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code.

## How to fix

- andialbrecht/sqlparse#698: inspect setup/pytest logs in the run folder.

## Per PR

### andialbrecht/sqlparse#698: feat(databricks): add initial databricks syntax

- Link: https://github.com/andialbrecht/sqlparse/pull/698 | author `sjrusso8` | head `c6ca23981037` | updated 2023-01-02 21:29 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = master @ 907fb496f90f (merge-base with the PR head); PR = PR head c6ca23981037
- Tested main SHA: `907fb496f90f` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `907fb496f90f` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Touched package files: sqlparse/filters/aligned_indent.py, sqlparse/keywords.py, sqlparse/lexer.py, sqlparse/sql.py
- Tests run: tests/test_parse.py, tests/test_tokenize.py, tests/test_keywords.py
- **Verdict: could_not_verify**: Contree could not prepare the main and PR sides (contree request failed: ApiTimeoutError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code.

#### Demo helper

These notes are background for the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: missing.
- Setup check: Nebius token: present.
- Setup check: free memory could not be read.
- Setup check: free disk 38.2 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 6 results
- Query: sqlparse python setup install instructions https://github.com/andialbrecht/sqlparse site:github.com/andialbrecht/sqlparse
- Query: sqlparse python documentation install https://github.com/andialbrecht/sqlparse site:github.com/andialbrecht/sqlparse
- Query: sqlparse python install requirements https://pypi.org/project/sqlparse/ https://github.com/andialbrecht/sqlparse site:pypi.org
- Source: sqlparse · PyPI — https://pypi.org/project/sqlparse/
- Source: GitHub - andialbrecht/sqlparse: A non-validating SQL parser module for Python · GitHub — https://github.com/andialbrecht/sqlparse
- Source: sqlparse/.github/workflows/python-app.yml at master · andialbrecht/sqlparse · GitHub — https://github.com/andialbrecht/sqlparse/blob/master/.github/workflows/python-app.yml
- Source: sqlparse/Makefile at master · andialbrecht/sqlparse · GitHub — https://github.com/andialbrecht/sqlparse/blob/master/Makefile
- Source: sqlparse/CHANGELOG at master · andialbrecht/sqlparse · GitHub — https://github.com/andialbrecht/sqlparse/blob/master/CHANGELOG
- Source: sqlparse/.readthedocs.yaml at master · andialbrecht/sqlparse · GitHub — https://github.com/andialbrecht/sqlparse/blob/master/.readthedocs.yaml
- Setup plan: the same packages on main and pr.
- Setup plan: install pytest (listed in the test extra) on main and pr.
- Setup plan: install pytest-cov (listed in the test extra) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.5, >=3.10
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 5556.9s total (tests 0s); logs: `sqlparse-698/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
