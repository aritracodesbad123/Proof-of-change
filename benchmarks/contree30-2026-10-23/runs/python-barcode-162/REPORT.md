# Proof-of-Change daily ops run: python-barcode-162

Started 2026-10-23 15:21 IST, finished 2026-10-23 15:23 IST, wall time 1.8 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [WhyNotHugo/python-barcode#162](https://github.com/WhyNotHugo/python-barcode/pull/162) | Add FNC4 to encode high (160–255) characters | source-pair | **could_not_verify** | no tests could be mapped to the touched files; probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- WhyNotHugo/python-barcode#162: could not verify: no tests could be mapped to the touched files; probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change

## How to fix

- WhyNotHugo/python-barcode#162: inspect setup/pytest logs in the run folder.

## Re-runs

Earlier attempts of this run date are kept under `superseded/attempt-N/` (records, logs, NOTE.md). The day's PR selection is frozen: this attempt re-tests every PR that any earlier attempt selected.

- **attempt-1**: attempt-1: superseded at 2026-10-23 15:21 IST. Selected 1 PR(s), 1 record(s).

Dropped between attempts (selected by an attempt, absent from the next attempt that selected PRs):

- none

| PR | attempt-1 | this run |
|---|---|---|
| WhyNotHugo/python-barcode#162 | could_not_verify | could_not_verify |

## Per PR

### WhyNotHugo/python-barcode#162: Add FNC4 to encode high (160–255) characters

- Link: https://github.com/WhyNotHugo/python-barcode/pull/162 | author `3mb3dw0rk5` | head `2628d270f7f1` | updated 2026-10-10 05:12 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ 880c890248d6 (merge-base with the PR head); PR = PR head 2628d270f7f1
- Tested main SHA: `880c890248d6` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `9522f94de7c6` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Touched package files: 
- Tests run: -
- **Verdict: could_not_verify**: no tests could be mapped to the touched files; probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change

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
- Looked up with Tavily: 4 results
- Query: python-barcode python setup install instructions https://github.com/WhyNotHugo/python-barcode site:github.com/WhyNotHugo/python-barcode
- Query: python-barcode python documentation install https://github.com/WhyNotHugo/python-barcode site:github.com/WhyNotHugo/python-barcode
- Query: python-barcode python install requirements https://pypi.org/project/python-barcode/ https://github.com/WhyNotHugo/python-barcode site:pypi.org
- Source: python-barcode/pyproject.toml at main · WhyNotHugo/python-barcode · GitHub — https://github.com/WhyNotHugo/python-barcode/blob/main/pyproject.toml
- Source: Unable to import barcode · Issue #63 · WhyNotHugo/python-barcode · GitHub — https://github.com/WhyNotHugo/python-barcode/issues/63
- Source: python-barcode/docs/changelog.rst at main · WhyNotHugo/python-barcode · GitHub — https://github.com/WhyNotHugo/python-barcode/blob/main/docs/changelog.rst
- Source: invalid ppem value with 0.15.1 but not with 0.14.0 · Issue #217 · WhyNotHugo/python-barcode · GitHub — https://github.com/WhyNotHugo/python-barcode/issues/217
- Setup plan: the same packages on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.9
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 106.4s total (tests 0s); logs: `python_barcode-162/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
