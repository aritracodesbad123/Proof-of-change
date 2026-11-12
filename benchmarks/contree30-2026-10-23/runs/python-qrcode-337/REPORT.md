# Proof-of-Change daily ops run: python-qrcode-337

Started 2026-10-23 14:24 IST, finished 2026-10-23 15:10 IST, wall time 46.8 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [lincolnloop/python-qrcode#337](https://github.com/lincolnloop/python-qrcode/pull/337) | Allow embedded image location to be erased before placing image | source-pair | **could_not_verify** | no tests could be mapped to the touched files |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- lincolnloop/python-qrcode#337: could not verify: no tests could be mapped to the touched files

## How to fix

- lincolnloop/python-qrcode#337: inspect setup/pytest logs in the run folder.

## Per PR

### lincolnloop/python-qrcode#337: Allow embedded image location to be erased before placing image

- Link: https://github.com/lincolnloop/python-qrcode/pull/337 | author `shanko07` | head `768d2ed4b660` | updated 2025-07-23 17:08 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ b80fea6ee7e7 (merge-base with the PR head); PR = PR head 768d2ed4b660
- Tested main SHA: `b80fea6ee7e7` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `ac2dda2ddef6` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Touched package files: 
- Tests run: -
- **Verdict: could_not_verify**: no tests could be mapped to the touched files

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
- Query: python-qrcode python setup install instructions https://github.com/lincolnloop/python-qrcode site:github.com/lincolnloop/python-qrcode
- Query: python-qrcode python documentation install https://github.com/lincolnloop/python-qrcode site:github.com/lincolnloop/python-qrcode
- Query: python-qrcode python install requirements https://pypi.org/project/python-qrcode/ https://github.com/lincolnloop/python-qrcode site:pypi.org
- Source: ImportError: No module named qrcode · Issue #103 — https://github.com/lincolnloop/python-qrcode/issues/103
- Source: Need to pip install colorama on Windows #131 — https://github.com/lincolnloop/python-qrcode/issues/131
- Source: import Image error · Issue #129 · lincolnloop/python-qrcode — https://github.com/lincolnloop/python-qrcode/issues/129
- Setup plan: the same packages on main and pr.
- Setup plan: colorama is noted, installed with the project.
- Setup plan: typing_extensions is noted, installed with the project.
- Setup plan: pypng is noted, installed with the project.
- Setup plan: install coverage (listed in the test extra) on main and pr.
- Setup plan: install pytest (listed in the test extra) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >= 3.7
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 2805.0s total (tests 0s); logs: `python_qrcode-337/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
