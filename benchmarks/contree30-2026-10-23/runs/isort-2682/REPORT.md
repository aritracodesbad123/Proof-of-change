# Proof-of-Change daily ops run: isort-2682

Started 2026-10-23 15:23 IST, finished 2026-10-23 15:28 IST, wall time 5.0 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [PyCQA/isort#2682](https://github.com/PyCQA/isort/pull/2682) | Fix split directives on complete multiline imports | source-pair | **could_not_verify** | could not verify: claim(s) C1, C2, C3, C1 (+9 more) expect a difference but no observation matches (156 test(s) ran on main, 173 on the PR; 17 new test(s) pass, 156 unchanged; probe model-p1 is not_ad |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 tested PRs have 3 alternating runs per side.
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- PyCQA/isort#2682: could not verify: could not verify: claim(s) C1, C2, C3, C1 (+9 more) expect a difference but no observation matches (156 test(s) ran on main, 173 on the PR; 17 new test(s) pass, 156 unchanged; probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-p2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-p3 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-p4 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count)

## How to fix

- PyCQA/isort#2682: inspect setup/pytest logs in the run folder.

## Re-runs

Earlier attempts of this run date are kept under `superseded/attempt-N/` (records, logs, NOTE.md). The day's PR selection is frozen: this attempt re-tests every PR that any earlier attempt selected.

- **attempt-1**: attempt-1: superseded at 2026-10-23 15:23 IST. Selected 0 PR(s), 0 record(s).

Dropped between attempts (selected by an attempt, absent from the next attempt that selected PRs):

- none

| PR | attempt-1 | this run |
|---|---|---|
| PyCQA/isort#2682 | - | could_not_verify |

## Per PR

### PyCQA/isort#2682: Fix split directives on complete multiline imports

- Link: https://github.com/PyCQA/isort/pull/2682 | author `hansu650` | head `147a248aede7` | updated 2026-09-28 11:54 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ a514c71ed86c (base tip = first parent of the merge commit); PR = GitHub test merge commit 2c3615a7a788 (refs/pull/2682/merge) of head 147a248aede7
- Tested main SHA: `a514c71ed86c` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `437147284d61` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Merge commit tested: `2c3615a7a78835f9087765d9d1d6d5dd3cb97d72` (refs/pull/2682/merge; parents `a514c71ed86c`, `147a248aede7`)
- Touched package files: isort/core.py, isort/parse.py
- Tests run: tests/unit/test_regressions.py, tests/unit/test_parse.py
- **Verdict: could_not_verify**: could not verify: claim(s) C1, C2, C3, C1 (+9 more) expect a difference but no observation matches (156 test(s) ran on main, 173 on the PR; 17 new test(s) pass, 156 unchanged; probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-p2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-p3 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-p4 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count)

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
- Query: isort python setup install instructions https://github.com/PyCQA/isort site:github.com/PyCQA/isort
- Query: isort python documentation install https://github.com/PyCQA/isort site:github.com/PyCQA/isort
- Query: isort python install requirements https://pypi.org/project/isort/ https://github.com/PyCQA/isort site:pypi.org
- Source: isort/pyproject.toml at main · PyCQA/isort · GitHub — https://github.com/PyCQA/isort/blob/main/pyproject.toml
- Source: isort — https://pypi.org/project/isort/
- Source: lint-python — https://pypi.org/project/lint-python/
- Source: GitHub - PyCQA/isort: A Python utility / library to sort imports. · GitHub — https://github.com/pycqa/isort
- Source: No CLI executable on Ubuntu 20.04 · Issue #1947 · PyCQA/isort · GitHub — https://github.com/PyCQA/isort/issues/1947
- Source: isort over Language Server Protocol and VS Code extension · Issue #1904 · PyCQA/isort · GitHub — https://github.com/PyCQA/isort/issues/1904
- Setup plan: the same packages on main and pr.
- Setup plan: mypy-extensions is noted, installed with the project.
- Setup plan: install bandit>=1.8.6 (listed in a dependency group) on main and pr.
- Setup plan: install black>=25.9.0 (listed in a dependency group) on main and pr.
- Setup plan: install colorama>=0.4.6 (listed in a dependency group) on main and pr.
- Setup plan: install coverage[toml]>=7.10.7 (listed in a dependency group) on main and pr.
- Setup plan: install example-isort-sorting-plugin>=0.1.0 (listed in a dependency group) on main and pr.
- Setup plan: install example-shared-isort-profile>=0.1.0 (listed in a dependency group) on main and pr.
- Setup plan: install flake8>=7.3.0 (listed in a dependency group) on main and pr.
- Setup plan: install flake8-bugbear>=24.12.12 (listed in a dependency group) on main and pr.
- Setup plan: install flake8-pyproject>=1.2.3 (listed in a dependency group) on main and pr.
- Setup plan: install hatch>=1.14.0 (listed in a dependency group) on main and pr.
- Setup plan: install hypothesis>=6.140.3 (listed in a dependency group) on main and pr.
- Setup plan: install hypothesmith>=0.3.3 (listed in a dependency group) on main and pr.
- Setup plan: install libcst>=1.9.0 (listed in a dependency group) on main and pr.
- Setup plan: install mypy>=2.3.1 (listed in a dependency group) on main and pr.
- Setup plan: install pep8-naming>=0.15.1 (listed in a dependency group) on main and pr.
- Setup plan: install pytest>=8.4.2 (listed in a dependency group) on main and pr.
- Setup plan: install pytest-benchmark>=5.1.0 (listed in a dependency group) on main and pr.
- Setup plan: install ruff>=0.13.3 (listed in a dependency group) on main and pr.
- Setup plan: install stdlibs>=2026.9.3 (listed in a dependency group) on main and pr.
- Setup plan: install tox>=4.30.3 (listed in a dependency group) on main and pr.
- Setup plan: install tox-uv>=1.28.0 (listed in a dependency group) on main and pr.
- Setup plan: install types-colorama>=0.4.2 (listed in a dependency group) on main and pr.
- Setup plan: install uv>=0.13.4 (listed in a dependency group) on main and pr.
- Setup plan: install myst-parser>=4.0.1 (listed in a dependency group) on main and pr.
- Setup plan: install sphinx>=7.4.7 (listed in a dependency group) on main and pr.
- Setup plan: install sphinx-immaterial>=0.13.9 (listed in a dependency group) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.11.0, >=3.10.0
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): 43 of 44 changed executable line(s) ran (98%); confidence normal
- Exit codes: all runs exited 0
- Runs: main#1 exit=0 5.8s 156 passed in 2.69s; pr#1 exit=0 5.9s 173 passed in 2.73s; main#2 exit=0 5.7s 156 passed in 2.50s; pr#2 exit=0 5.8s 173 passed in 2.57s; main#3 exit=0 5.8s 156 passed in 2.50s; pr#3 exit=0 5.5s 173 passed in 2.58s
- Duration: 299.7s total (tests 34.5s); logs: `isort-2682/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
