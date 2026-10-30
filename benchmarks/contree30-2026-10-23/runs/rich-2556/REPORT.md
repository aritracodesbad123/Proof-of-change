# Proof-of-Change daily ops run: rich-2556

Started 2026-10-23 16:05 IST, finished 2026-10-23 16:38 IST, wall time 33.0 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [Textualize/rich#2556](https://github.com/Textualize/rich/pull/2556) | feat(terminal_theme): add more themes | source-pair | **could_not_verify** | Contree could not prepare the main and PR sides (contree request failed: ContreeTransportError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-reques |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- Textualize/rich#2556: could not verify: Contree could not prepare the main and PR sides (contree request failed: ContreeTransportError). In Contree mode nothing from the pull request runs locally, so Proof-of-Change will not run pull-request code.

## How to fix

- Textualize/rich#2556: inspect setup/pytest logs in the run folder.

## Per PR

### Textualize/rich#2556: feat(terminal_theme): add more themes

- Link: https://github.com/Textualize/rich/pull/2556 | author `wizard-28` | head `e7dcde138f57` | updated 2026-06-15 13:48 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ 9d8f9a372cc5 (base tip = first parent of the merge commit); PR = GitHub test merge commit b4021e717066 (refs/pull/2556/merge) of head e7dcde138f57
- Tested main SHA: `9d8f9a372cc5` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `13dd9c2c2ebe` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Merge commit tested: `b4021e7170666a6ba722089115051b5e29d0de51` (refs/pull/2556/merge; parents `9d8f9a372cc5`, `e7dcde138f57`)
- Touched package files: rich/terminal_theme.py
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
- Query: rich python setup install instructions https://github.com/Textualize/rich site:github.com/Textualize/rich
- Query: rich python documentation install https://github.com/Textualize/rich site:github.com/Textualize/rich
- Query: rich python install requirements https://pypi.org/project/rich/ https://github.com/Textualize/rich site:pypi.org
- Source: rich-pyfiglet — https://pypi.org/project/rich-pyfiglet/
- Source: GitHub - Textualize/rich: Rich is a Python library for rich text and beautiful formatting in the terminal. · GitHub — https://github.com/textualize/rich
- Source: GitHub - Textualize/rich-cli: Rich-cli is a command line toolbox for fancy output in the terminal · GitHub — https://github.com/textualize/rich-cli
- Source: [BUG] `rich` reverts to legacy Windows APIs when stdout is redirected · Issue #3437 · Textualize/rich · GitHub — https://github.com/Textualize/rich/issues/3437
- Setup plan: the same packages on main and pr.
- Setup plan: install alabaster==1.0.0 (listed in requirements.txt) on main and pr.
- Setup plan: install Sphinx==8.2.3 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinx-rtd-theme==3.0.2 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinx-copybutton==0.5.2 (listed in requirements.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.9.0
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Setup plan: refused rich-cli: its PyPI page does not link to this GitHub repository
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 1981.2s total (tests 0s); logs: `rich-2556/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
