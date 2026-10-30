# Proof-of-Change daily ops run: boltons-43

Started 2026-10-23 15:19 IST, finished 2026-10-23 15:21 IST, wall time 2.0 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **REJECT**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [mahmoud/boltons#43](https://github.com/mahmoud/boltons/pull/43) | join function for iterutils | source-pair | **could_not_verify** | tests produced no results on one side (collection failed; see pytest logs); probe model-probe1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count  |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 0/1 tested PRs have 3 alternating runs per side.
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- mahmoud/boltons#43: could not verify: tests produced no results on one side (collection failed; see pytest logs); probe model-probe1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change

## How to fix

- mahmoud/boltons#43: inspect setup/pytest logs in the run folder.

## Re-runs

Earlier attempts of this run date are kept under `superseded/attempt-N/` (records, logs, NOTE.md). The day's PR selection is frozen: this attempt re-tests every PR that any earlier attempt selected.

- **attempt-1**: attempt-1: superseded at 2026-10-23 15:19 IST. Selected 1 PR(s), 0 record(s).

Dropped between attempts (selected by an attempt, absent from the next attempt that selected PRs):

- none

| PR | attempt-1 | this run |
|---|---|---|
| mahmoud/boltons#43 | selected, no record | could_not_verify |

## Per PR

### mahmoud/boltons#43: join function for iterutils

- Link: https://github.com/mahmoud/boltons/pull/43 | author `fivetentaylor` | head `750b91072192` | updated 2016-08-03 14:41 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = master @ 5b78fecfb976 (merge-base with the PR head); PR = PR head 750b91072192
- Tested main SHA: `5b78fecfb976` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `4140386d1fb1` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Touched package files: boltons/iterutils.py
- Tests run: tests, tests/test_iterutils.py
- **Verdict: could_not_verify**: tests produced no results on one side (collection failed; see pytest logs); probe model-probe1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change

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
- Looked up with Tavily: 6 results
- Query: boltons python setup install instructions https://github.com/mahmoud/boltons site:github.com/mahmoud/boltons
- Query: boltons python documentation install https://github.com/mahmoud/boltons site:github.com/mahmoud/boltons
- Query: boltons python install requirements https://pypi.org/project/boltons/ https://github.com/mahmoud/boltons site:pypi.org
- Source: boltons · PyPI — https://pypi.org/project/boltons/
- Source: types-boltons · PyPI — https://pypi.org/project/types-boltons/
- Source: Improve Test Suite Documentation · Issue #390 · mahmoud/boltons · GitHub — https://github.com/mahmoud/boltons/issues/390
- Source: boltons/.readthedocs.yaml at master · mahmoud/boltons · GitHub — https://github.com/mahmoud/boltons/blob/master/.readthedocs.yaml
- Source: boltons/docs/index.rst at master · mahmoud/boltons · GitHub — https://github.com/mahmoud/boltons/blob/master/docs/index.rst
- Source: boltons/boltons/tbutils.py at master · mahmoud/boltons — https://github.com/mahmoud/boltons/blob/master/boltons/tbutils.py
- Setup plan: the same packages on main and pr.
- Setup plan: install sphinxcontrib-napoleon (listed in requirements-rtd.txt) on main and pr.
- Setup plan: install py==1.4.26 (listed in requirements-test.txt) on main and pr.
- Setup plan: install pytest==2.7.0 (listed in requirements-test.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.7
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: main#1 exit=1 1.4s AttributeError: __spec__; pr#1 exit=1 1.4s AttributeError: __spec__; main#2 exit=1 1.4s AttributeError: __spec__; pr#2 exit=1 1.4s AttributeError: __spec__; main#3 exit=1 1.4s AttributeError: __spec__; pr#3 exit=1 1.4s AttributeError: __spec__
- Duration: 119.3s total (tests 8.4s); logs: `boltons-43/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
