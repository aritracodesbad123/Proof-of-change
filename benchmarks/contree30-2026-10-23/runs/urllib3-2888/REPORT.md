# Proof-of-Change daily ops run: urllib3-2888

Started 2026-10-23 20:47 IST, finished 2026-10-24 02:17 IST, wall time 330.3 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [urllib3/urllib3#2888](https://github.com/urllib3/urllib3/pull/2888) | Keep hostname's trailing dot | source-pair | rerun, setup problem | git step failed (128): git -C <home>/Desktop/Proof-of-Change/proof-of-change/ops/runs/contree30/work/urllib3-2888/src fetch |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- urllib3/urllib3#2888: rerun, setup problem (git step failed (128): git -C <home>/Desktop/Proof-of-Change/proof-of-change/ops/runs/contree30/work/urllib3-2888/src fetch)

## How to fix

- urllib3/urllib3#2888: this was retried as a setup problem and is not counted as a verdict.

## Per PR

### urllib3/urllib3#2888: Keep hostname's trailing dot

- Link: https://github.com/urllib3/urllib3/pull/2888 | author `zhanpon` | head `b9d9e2b8bf61` | updated 2023-11-24 09:38 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Touched package files: src/urllib3/connection.py
- Tests run: -
- **Not a verdict:** rerun, setup problem

#### Demo helper

These notes are background for the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: missing.
- Setup check: Nebius token: present.
- Setup check: free memory could not be read.
- Setup check: free disk 37.0 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 3 results
- Query: urllib3 python setup install instructions https://github.com/urllib3/urllib3 site:github.com/urllib3/urllib3
- Query: urllib3 python documentation install https://github.com/urllib3/urllib3 site:github.com/urllib3/urllib3
- Query: urllib3 python install requirements https://pypi.org/project/urllib3/ https://github.com/urllib3/urllib3 site:pypi.org
- Source: GitHub - urllib3/urllib3: urllib3 is a user-friendly HTTP client library for Python · GitHub — https://github.com/urllib3/urllib3
- Source: GitHub - urllib3/urllib3 at zzun.app · GitHub — https://github.com/urllib3/urllib3?ref=zzun.app
- Source: urllib3/docs/user-guide.rst at main · urllib3/urllib3 · GitHub — https://github.com/urllib3/urllib3/blob/main/docs/user-guide.rst
- rerun, setup problem: source checkout failed after 3 tries.
- Demo helper: setup failure already labelled; the probe was not rerun.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 19817.5s total (tests 0s); logs: `urllib3-2888/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
