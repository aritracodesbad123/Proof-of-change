# Proof-of-Change daily ops run: invoke-957

Started 2026-10-24 07:14 IST, finished 2026-10-24 07:16 IST, wall time 2.2 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [pyinvoke/invoke#957](https://github.com/pyinvoke/invoke/pull/957) | Default run.shell to /bin/sh | source-pair | **could_not_verify** | no tests could be mapped to the touched files; probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- pyinvoke/invoke#957: could not verify: no tests could be mapped to the touched files; probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change

## How to fix

- pyinvoke/invoke#957: inspect setup/pytest logs in the run folder.

## Per PR

### pyinvoke/invoke#957: Default run.shell to /bin/sh

- Link: https://github.com/pyinvoke/invoke/pull/957 | author `tobim` | head `967a6d11ae87` | updated 2026-04-06 05:10 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ ee9d862540f0 (merge-base with the PR head); PR = PR head 967a6d11ae87
- Tested main SHA: `ee9d862540f0` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `2e6609818ffa` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Touched package files: invoke/config.py, invoke/runners.py
- Tests run: -
- **Verdict: could_not_verify**: no tests could be mapped to the touched files; probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change

#### Demo helper

These notes are background for the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: missing.
- Setup check: Nebius token: present.
- Setup check: free memory could not be read.
- Setup check: free disk 38.3 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 9 results
- Query: invoke python setup install instructions https://github.com/pyinvoke/invoke site:github.com/pyinvoke/invoke
- Query: invoke python documentation install https://github.com/pyinvoke/invoke site:github.com/pyinvoke/invoke
- Query: invoke python install requirements https://pypi.org/project/invoke/ https://github.com/pyinvoke/invoke site:pypi.org
- Source: invoke/pyproject.toml at main · pyinvoke/invoke · GitHub — https://github.com/pyinvoke/invoke/tree/main/pyproject.toml
- Source: invoke · PyPI — https://pypi.org/project/invoke/
- Source: neoxelox-invoke · PyPI — https://pypi.org/project/neoxelox-invoke/
- Source: Documentation for users of invoke based projects · Issue #1020 · pyinvoke/invoke · GitHub — https://github.com/pyinvoke/invoke/issues/1020
- Source: Instructions to install dev version don't work · Issue #391 · pyinvoke/invoke · GitHub — https://github.com/pyinvoke/invoke/issues/391
- Source: invoke/invoke/runners.py at main · pyinvoke/invoke · GitHub — https://github.com/pyinvoke/invoke/blob/master/invoke/runners.py
- Source: Logging & other output concerns · Issue #15 · pyinvoke/invoke · GitHub — https://github.com/pyinvoke/invoke/issues/15
- Source: Issue with Python 3.11, or type annotations: the inspect module changed · Issue #833 · pyinvoke/invoke · GitHub — https://github.com/pyinvoke/invoke/issues/833
- Source: PyPI · The Python Package Index — https://pypi.org
- Setup plan: the same packages on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.6, >=3.9
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 131.3s total (tests 0s); logs: `invoke-957/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
