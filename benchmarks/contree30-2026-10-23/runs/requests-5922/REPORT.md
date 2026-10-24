# Proof-of-Change daily ops run: requests-5922

Started 2026-10-23 15:50 IST, finished 2026-10-23 16:05 IST, wall time 14.7 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [psf/requests#5922](https://github.com/psf/requests/pull/5922) | Always use value of session.verify when set, fixes #5921 | source-pair | **could_not_verify** | Contree could not prepare the main and PR sides (contree request failed: ApiTimeoutError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- psf/requests#5922: could not verify: Contree could not prepare the main and PR sides (contree request failed: ApiTimeoutError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code.

## How to fix

- psf/requests#5922: inspect setup/pytest logs in the run folder.

## Per PR

### psf/requests#5922: Always use value of session.verify when set, fixes #5921

- Link: https://github.com/psf/requests/pull/5922 | author `brmzkw` | head `62b3d6a26ad2` | updated 2021-09-01 18:17 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ aae78010e987 (merge-base with the PR head); PR = PR head 62b3d6a26ad2
- Tested main SHA: `aae78010e987` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `aae78010e987` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Touched package files: requests/sessions.py
- Tests run: tests/test_requests.py
- **Verdict: could_not_verify**: Contree could not prepare the main and PR sides (contree request failed: ApiTimeoutError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code.

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
- Query: requests python setup install instructions https://github.com/psf/requests site:github.com/psf/requests
- Query: requests python documentation install https://github.com/psf/requests site:github.com/psf/requests
- Query: requests python install requirements https://pypi.org/project/requests/ https://github.com/psf/requests site:pypi.org
- Source: requests/docs/user/install.rst at main · psf/requests · GitHub — https://github.com/psf/requests/blob/main/docs/user/install.rst
- Source: GitHub - psf/requests at blog.datachef.co · GitHub — https://github.com/psf/requests?ref=blog.datachef.co
- Source: requests/docs/user/advanced.rst at main · psf/requests · GitHub — https://github.com/psf/requests/blob/master/docs/user/advanced.rst
- Source: Python Requests - GeeksforGeeks — https://geeksforgeeks.org/python/python-requests-tutorial
- Source: Requests (software) - Wikipedia — https://en.wikipedia.org/wiki/Requests_(software)
- Source: Requests: HTTP for Humans™ — Requests 2.34.2 documentation — https://requests.readthedocs.io
- Setup plan: the same packages on main and pr.
- Setup plan: install pytest>=2.8.0,<=3.10.1 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pytest-cov (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pytest-httpbin==1.0.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pytest-mock==2.0.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install httpbin==0.7.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install Flask>=1.0,<2.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install trustme (listed in requirements-dev.txt) on main and pr.
- Setup plan: install wheel (listed in requirements-dev.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*, >=3.10
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 879.3s total (tests 0s); logs: `requests-5922/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
