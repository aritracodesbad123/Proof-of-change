# Proof-of-Change daily ops run: loguru-86

Started 2026-10-24 02:33 IST, finished 2026-10-24 07:11 IST, wall time 278.1 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [Delgan/loguru#86](https://github.com/Delgan/loguru/pull/86) | [RFC] Allow to configure exception formatter | source-pair | **could_not_verify** | Contree could not prepare the main and PR sides (contree request failed: ApiTimeoutError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- Delgan/loguru#86: could not verify: Contree could not prepare the main and PR sides (contree request failed: ApiTimeoutError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code.

## How to fix

- Delgan/loguru#86: inspect setup/pytest logs in the run folder.

## Per PR

### Delgan/loguru#86: [RFC] Allow to configure exception formatter

- Link: https://github.com/Delgan/loguru/pull/86 | author `blueyed` | head `e99e482c05f8` | updated 2023-09-11 20:41 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = master @ 770b17815b8c (merge-base with the PR head); PR = PR head e99e482c05f8
- Tested main SHA: `770b17815b8c` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `e1f48c91cf26` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Touched package files: loguru/_handler.py, loguru/_logger.py
- Tests run: tests/test_formatting.py
- **Verdict: could_not_verify**: Contree could not prepare the main and PR sides (contree request failed: ApiTimeoutError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code.

#### Demo helper

These notes are background for the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: missing.
- Setup check: Nebius token: present.
- Setup check: free memory could not be read.
- Setup check: free disk 37.1 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 7 results
- Query: loguru python setup install instructions https://github.com/Delgan/loguru site:github.com/Delgan/loguru
- Query: loguru python documentation install https://github.com/Delgan/loguru site:github.com/Delgan/loguru
- Query: loguru python install requirements https://pypi.org/project/loguru/ https://github.com/Delgan/loguru site:pypi.org
- Source: loguru/pyproject.toml at master · Delgan/loguru · GitHub — https://github.com/Delgan/loguru/blob/master/pyproject.toml
- Source: loguru — https://pypi.org/project/loguru/
- Source: Python Logging (beans-logging) — https://pypi.org/project/beans-logging/
- Source: lager — https://pypi.org/project/lager/
- Source: loguru/.github/workflows/tests.yml at 4abaa1627c17140efa8bc4c0769aab5cc1ac8bb4 · Delgan/loguru · GitHub — https://github.com/Delgan/loguru/blob/4abaa1627c17140efa8bc4c0769aab5cc1ac8bb4/.github/workflows/tests.yml
- Source: loguru/.github/workflows/tests.yml at af132472ce31368a3c238180d1a5b45101c7cd8f · Delgan/loguru · GitHub — https://github.com/Delgan/loguru/blob/af132472ce31368a3c238180d1a5b45101c7cd8f/.github/workflows/tests.yml
- Source: Issues · Delgan/loguru · GitHub — https://github.com/Delgan/loguru/issues
- Setup plan: the same packages on main and pr.
- Setup plan: ansimarkup is noted, installed with the project.
- Setup plan: colorama is noted, installed with the project.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.5, <4.0,>=3.5
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 16686.5s total (tests 0s); logs: `loguru-86/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
