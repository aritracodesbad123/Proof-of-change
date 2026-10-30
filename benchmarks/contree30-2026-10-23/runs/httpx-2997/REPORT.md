# Proof-of-Change daily ops run: httpx-2997

Started 2026-10-23 16:49 IST, finished 2026-10-23 20:47 IST, wall time 237.6 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [encode/httpx#2997](https://github.com/encode/httpx/pull/2997) | Fixing missed arguments for pools when init transports | source-pair | **could_not_verify** | Contree could not prepare the main and PR sides (contree request failed: ContreeTransportError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-reques |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- encode/httpx#2997: could not verify: Contree could not prepare the main and PR sides (contree request failed: ContreeTransportError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code.

## How to fix

- encode/httpx#2997: inspect setup/pytest logs in the run folder.

## Per PR

### encode/httpx#2997: Fixing missed arguments for pools when init transports

- Link: https://github.com/encode/httpx/pull/2997 | author `NewUserHa` | head `2b11bcddf78f` | updated 2023-12-15 03:52 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = master @ 3b9060ee1121 (merge-base with the PR head); PR = PR head 2b11bcddf78f
- Tested main SHA: `3b9060ee1121` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `3b9060ee1121` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Touched package files: httpx/_transports/default.py
- Tests run: -
- **Verdict: could_not_verify**: Contree could not prepare the main and PR sides (contree request failed: ContreeTransportError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code.

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
- Query: httpx python setup install instructions https://github.com/encode/httpx site:github.com/encode/httpx
- Query: httpx python documentation install https://github.com/encode/httpx site:github.com/encode/httpx
- Query: httpx python install requirements https://pypi.org/project/httpx/ https://github.com/encode/httpx site:pypi.org
- Source: GitHub - encode/httpx: A next generation HTTP client for Python. 🦋 · GitHub — https://github.com/encode/httpx
- Source: Version 1.0 public call. 👋🏼 · encode/httpx · Discussion #3344 · GitHub — https://github.com/encode/httpx/discussions/3344
- Source: httpx/CHANGELOG.md at master · encode/httpx · GitHub — https://github.com/encode/httpx/blob/master/CHANGELOG.md
- Source: httpx/docs/contributing.md at master · encode/httpx · GitHub — https://github.com/encode/httpx/blob/master/docs/contributing.md
- Setup plan: the same packages on main and pr.
- Setup plan: certifi is noted, installed with the project.
- Setup plan: httpcore is noted, installed with the project.
- Setup plan: anyio is noted, installed with the project.
- Setup plan: idna is noted, installed with the project.
- Setup plan: sniffio is noted, installed with the project.
- Setup plan: install chardet==5.2.0 (listed in requirements.txt) on main and pr.
- Setup plan: install types-chardet==5.0.4.5 (listed in requirements.txt) on main and pr.
- Setup plan: install mkdocs==1.5.3 (listed in requirements.txt) on main and pr.
- Setup plan: install mkautodoc==0.2.0 (listed in requirements.txt) on main and pr.
- Setup plan: install mkdocs-material==9.4.14 (listed in requirements.txt) on main and pr.
- Setup plan: install build==1.0.3 (listed in requirements.txt) on main and pr.
- Setup plan: install twine==4.0.2 (listed in requirements.txt) on main and pr.
- Setup plan: install coverage[toml]==7.3.0 (listed in requirements.txt) on main and pr.
- Setup plan: install cryptography==41.0.7 (listed in requirements.txt) on main and pr.
- Setup plan: install mypy==1.5.1 (listed in requirements.txt) on main and pr.
- Setup plan: install types-certifi==2021.10.8.2 (listed in requirements.txt) on main and pr.
- Setup plan: install pytest==7.4.3 (listed in requirements.txt) on main and pr.
- Setup plan: install ruff==0.1.6 (listed in requirements.txt) on main and pr.
- Setup plan: install trio==0.22.2 (listed in requirements.txt) on main and pr.
- Setup plan: install trio-typing==0.10.0 (listed in requirements.txt) on main and pr.
- Setup plan: install trustme==1.1.0 (listed in requirements.txt) on main and pr.
- Setup plan: install uvicorn==0.24.0.post1 (listed in requirements.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.8
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Setup plan: refused be: its PyPI page does not link to this GitHub repository
- Setup plan: refused published: its PyPI page does not link to this GitHub repository
- Setup plan: refused under: its PyPI page does not link to this GitHub repository
- Setup plan: refused s: its PyPI page does not link to this GitHub repository
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 14257.3s total (tests 0s); logs: `httpx-2997/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
