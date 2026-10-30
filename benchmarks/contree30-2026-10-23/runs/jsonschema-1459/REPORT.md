# Proof-of-Change daily ops run: jsonschema-1459

Started 2026-10-23 15:28 IST, finished 2026-10-23 15:32 IST, wall time 4.3 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [python-jsonschema/jsonschema#1459](https://github.com/python-jsonschema/jsonschema/pull/1459) | Fix multipleOf with integer-valued float for large integers | source-pair | **could_not_verify** | Coverage wasn't measured, so this can't be marked verified (coverage run produced no data; see coverage-pytest.log) (tests: 304 test(s) ran on main, 305 on the PR; 1 new test(s) pass, 304 unchanged) |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 tested PRs have 3 alternating runs per side.
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- python-jsonschema/jsonschema#1459: could not verify: Coverage wasn't measured, so this can't be marked verified (coverage run produced no data; see coverage-pytest.log) (tests: 304 test(s) ran on main, 305 on the PR; 1 new test(s) pass, 304 unchanged)

## How to fix

- python-jsonschema/jsonschema#1459: inspect setup/pytest logs in the run folder.

## Per PR

### python-jsonschema/jsonschema#1459: Fix multipleOf with integer-valued float for large integers

- Link: https://github.com/python-jsonschema/jsonschema/pull/1459 | author `worksbyfriday` | head `08a8c22576d5` | updated 2026-08-01 23:11 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ c497561ea0a9 (base tip = first parent of the merge commit); PR = GitHub test merge commit 7317cdc9976d (refs/pull/1459/merge) of head 08a8c22576d5
- Tested main SHA: `c497561ea0a9` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `5a5fa97c7d54` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Merge commit tested: `7317cdc9976d85c21b887b73fdc787df496922f4` (refs/pull/1459/merge; parents `c497561ea0a9`, `08a8c22576d5`)
- Touched package files: jsonschema/_keywords.py, jsonschema/tests/test_validators.py
- Tests run: jsonschema/tests/test_validators.py
- **Verdict: could_not_verify**: Coverage wasn't measured, so this can't be marked verified (coverage run produced no data; see coverage-pytest.log) (tests: 304 test(s) ran on main, 305 on the PR; 1 new test(s) pass, 304 unchanged)

#### Demo helper

These notes are background for the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: missing.
- Setup check: Nebius token: present.
- Setup check: free memory could not be read.
- Setup check: free disk 37.3 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 3 results
- Query: jsonschema python setup install instructions https://github.com/python-jsonschema/jsonschema site:github.com/python-jsonschema/jsonschema
- Query: jsonschema python documentation install https://github.com/python-jsonschema/jsonschema site:github.com/python-jsonschema/jsonschema
- Query: jsonschema python install requirements https://pypi.org/project/jsonschema/ https://github.com/python-jsonschema/jsonschema site:pypi.org
- Source: GitHub - python-jsonschema/jsonschema: An implementation of the JSON Schema specification for Python · GitHub — https://github.com/python-jsonschema/jsonschema
- Source: Relative URI $refs returning "unknown url type" · Issue #313 · python-jsonschema/jsonschema · GitHub — https://github.com/python-jsonschema/jsonschema/issues/313
- Source: incorrect anyOf validation error · Issue #598 · python-jsonschema/jsonschema · GitHub — https://github.com/python-jsonschema/jsonschema/issues/598
- Setup plan: the same packages on main and pr.
- Setup plan: attrs is noted, installed with the project.
- Setup plan: jsonschema-specifications is noted, installed with the project.
- Setup plan: referencing is noted, installed with the project.
- Setup plan: rpds-py is noted, installed with the project.
- Setup plan: install virtue (listed in the test extra) on main and pr.
- Setup plan: install jsonpath-ng (listed in the test extra) on main and pr.
- Setup plan: install pyperf (listed in a dependency group) on main and pr.
- Setup plan: install furo (listed in a dependency group) on main and pr.
- Setup plan: install lxml (listed in a dependency group) on main and pr.
- Setup plan: install sphinx<9 (listed in a dependency group) on main and pr.
- Setup plan: install sphinx-autoapi (listed in a dependency group) on main and pr.
- Setup plan: install sphinx-autodoc-typehints (listed in a dependency group) on main and pr.
- Setup plan: install sphinx-copybutton (listed in a dependency group) on main and pr.
- Setup plan: install sphinx-json-schema-spec (listed in a dependency group) on main and pr.
- Setup plan: install sphinxcontrib-spelling>5 (listed in a dependency group) on main and pr.
- Setup plan: install sphinxext-opengraph (listed in a dependency group) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.12, >=3.10
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (coverage run produced no data; see coverage-pytest.log); confidence none; **changed the verdict** (was verified)
- Exit codes: all runs exited 0
- Runs: main#1 exit=0 2.8s 304 passed in 0.82s; pr#1 exit=0 2.8s 305 passed in 0.89s; main#2 exit=0 2.9s 304 passed in 0.85s; pr#2 exit=0 2.9s 305 passed in 0.90s; main#3 exit=0 2.9s 304 passed in 0.85s; pr#3 exit=0 2.8s 305 passed in 0.84s
- Duration: 259.7s total (tests 17.1s); logs: `jsonschema-1459/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
