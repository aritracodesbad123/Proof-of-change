# Reviewer report: optiland/optiland#962: Align dock and document tabs at the top

Run `optiland-962`, tested 2026-10-22 01:22 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 01:28 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Align dock and document tabs at the top ([optiland/optiland#962](https://github.com/optiland/optiland/pull/962)).
- **What we observed:** could not verify: setup gap setup.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 4.5 GB (of 15.6 GB).
- Setup check: free disk 92.8 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 3 results
- Query: optiland python setup install instructions https://github.com/optiland/optiland site:github.com/optiland/optiland
- Query: optiland python documentation install https://github.com/optiland/optiland site:github.com/optiland/optiland
- Query: optiland python install requirements https://pypi.org/project/optiland/ https://github.com/optiland/optiland site:pypi.org
- Source: optiland/pyproject.toml at master — https://github.com/optiland/optiland/blob/master/pyproject.toml
- Source: GitHub - optiland/optiland: Comprehensive optical design, optimization, and analysis in Python, including GPU-accelerated and differentiable ray tracing via PyTorch. · GitHub — https://github.com/optiland/optiland
- Source: Raytracing / Simulating LED in enclosed compartments · optiland/optiland · Discussion #96 · GitHub — https://github.com/optiland/optiland/discussions/96
- Setup plan: the same packages on main and pr.
- Setup plan: numpy is noted, installed with the project.
- Setup plan: scipy is noted, installed with the project.
- Setup plan: pandas is noted, installed with the project.
- Setup plan: pyyaml is noted, installed with the project.
- Setup plan: matplotlib is noted, installed with the project.
- Setup plan: vtk is noted, installed with the project.
- Setup plan: tabulate is noted, installed with the project.
- Setup plan: numba is noted, installed with the project.
- Setup plan: requests is noted, installed with the project.
- Setup plan: seaborn is noted, installed with the project.
- Setup plan: typing-extensions is noted, installed with the project.
- Setup plan: install sphinx==8.2.3 (listed in requirements.txt) on main and pr.
- Setup plan: install docutils==0.21.2 (listed in requirements.txt) on main and pr.
- Setup plan: install pydata-sphinx-theme==0.21.0 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinx-design==0.7.0 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinx-copybutton==0.5.2 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinx-sitemap==2.9.0 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinx-notfound-page==1.1.0 (listed in requirements.txt) on main and pr.
- Setup plan: install Pygments==2.21.0 (listed in requirements.txt) on main and pr.
- Setup plan: install nbsphinx==0.9.8 (listed in requirements.txt) on main and pr.
- Setup plan: install ipython==9.17.0 (listed in requirements.txt) on main and pr.
- Setup plan: install jupyterlite-sphinx==0.23.0 (listed in requirements.txt) on main and pr.
- Setup plan: install jupyterlite-xeus==5.0.0 (listed in requirements.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.11
- Installed sphinx 8.2.3 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed docutils 0.21.2 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed pydata-sphinx-theme 0.21.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed sphinx-design 0.7.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed sphinx-copybutton 0.5.2 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed sphinx-sitemap 2.9.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed sphinx-notfound-page 1.1.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed Pygments 2.21.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed nbsphinx 0.9.8 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed ipython 9.17.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed jupyterlite-sphinx 0.23.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed jupyterlite-xeus 5.0.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Before rerun: could_not_verify: no test actually ran on the PR side: 3 test(s) ran on main, 0 on the PR; 0 new test(s) pass, 0 unchanged; 1 test module(s) fail to load on both sides (tests.gui.test_surface_properties_panels), so their tests did not run; test module tests.gui.test_document_view_preferences fails to load on the PR side (3 test(s) no longer run); test module tests.gui.test_tab_placement fails to load on the PR side (0 test(s) no longer run); probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count
- After rerun: not rerun. could not verify: setup gap setup

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (0 unchanged, 3 runs per side) | [pytest-pr-1.log:43](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-pr-1.log) «3 errors in 5.62s» |
| P-C1 | After the change, outer docks, nested script docks, viewer, script, optimization, and surface-property tab widgets will have their tabs placed at the top (North) consistently. (PR description) | ⚪ **not testable** | probe model-p1, probe.error: same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-p1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0122/optiland-962/probe-model-p1-pr-1.jsonl) «"observation": "probe.error"» |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 2 test module(s) fail to load on the PR side only (their tests no longer run), e.g. tests.gui.test_document_view_preferences (3 test(s) on the other side) | [pytest-pr-1.log:43](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-pr-1.log) «3 errors in 5.62s» |

Citation check (PASS): 3 citation(s), every one re-read from its log file and matched.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 3 / 0 | - |
| Tests unchanged | 0 | - |
| New tests that pass | 0 | - |
| Tests that pass on main but fail on the PR | 0 | - |
| Tests that are new in the PR and fail | 0 | - |
| Tests that ran on main but are missing on the PR side | 0 | - |
| Tests that changed result in another way (for example passed -> skipped) | 0 | - |
| Tests that gave different results between the 3 runs of the same side (flaky) | 0 | - |
| Tests that fail on main and pass on the PR | 0 | - |
| Tests that are new or changed but did not run because an optional module is missing | 0 | - |
| Tests that were re-parametrized (same test, new parameter ids; not counted as removed) | 0 | - |
| Test modules that fail to load on the PR side only (their tests no longer run) | 2 | `tests.gui.test_document_view_preferences (3 test(s) on the other side)`, `tests.gui.test_tab_placement (0 test(s) on the other side)` |
| Test modules that fail to load on main only (no baseline for their tests) | 0 | - |
| Test modules that fail to load on both sides (their tests did not run) | 1 | `tests.gui.test_surface_properties_panels` |
| Tests that fail identically on both sides (already broken on main) | 0 | - |

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-p1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-p1.py`, frozen `f6837713af42` at 2026-10-21T19:56:50.058441+00:00): Check tab positions of tab widgets in docks and lens editor surface properties

- P-C1 (PR description): After the change, outer docks, nested script docks, viewer, script, optimization, and surface-property tab widgets will have their tabs placed at the top (North) consistently. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | P-C1 | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-p1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0122/optiland-962/probe-model-p1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-p1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0122/optiland-962/probe-model-p1-pr-1.jsonl) «"observation": "probe.error"» |

Citation check (PASS): 2 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: NOT MEASURED** (coverage run produced no data (exit 1); see coverage-pytest.log).

Coverage gate (python, confidence lower): coverage of the changed Python lines was NOT MEASURED (coverage run produced no data (exit 1); see coverage-pytest.log).

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `9fd0f199e62e` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every claim cites a real log line: 3 citation(s), every one re-read from its log file and matched.
- Every probe observation cites its output line: 2 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | could not verify: setup gap setup | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| pytest exit codes explained | 🔴 **FAIL** | pytest exit 1; no identical pre-existing failures | Read the pytest logs: PR run 1: 2 failure(s) not seen on main; PR run 2: 2 failure(s) not seen on main |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (coverage run produced no data (exit 1); see coverage-pytest.log) | The coverage run did not produce data (see coverage.why); run the check again. |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🔴 **FAIL** | pytest exit 1; no identical pre-existing failures |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (coverage run produced no data (exit 1); see coverage-pytest.log) |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟢 **PASS** | 3 citation(s), every one re-read from its log file and matched |
| Every probe observation cites its output line | 🟢 **PASS** | 2 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/optiland-962 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/optiland/optiland/pull/962
```

## Evidence links

- [Pull request optiland/optiland#962](https://github.com/optiland/optiland/pull/962)
- [record.json](../../ops/runs/2026-10-22-check-0122/optiland-962/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0122/optiland-962/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0122/optiland-962/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0122/optiland-962/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0122/optiland-962/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0122/optiland-962/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0122/optiland-962/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0122/optiland-962/coverage-pytest.log)
- [probe-model-p1-main-1.jsonl](../../ops/runs/2026-10-22-check-0122/optiland-962/probe-model-p1-main-1.jsonl)
- [probe-model-p1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0122/optiland-962/probe-model-p1-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:54](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-main-1.log) «4 errors in 6.05s»
- pr run 1 result: [pytest-pr-1.log:43](../../ops/runs/2026-10-22-check-0122/optiland-962/pytest-pr-1.log) «3 errors in 5.62s»

## Glossary

| Term | Meaning |
|---|---|
| main | The library as it is today, without the PR. |
| PR | Pull request: a proposed change to the library. |
| run | One full pass of the selected tests. We do 3 per side, alternating main and PR. |
| flaky | A test that gives different results when nothing changed; it is ignored as evidence. |
| log line | A line in a pytest-*.log file: the raw output the verdict is based on. |
| route | How the two sides were built: nightly+patch, source-build or source-pair (see docs/OPERATIONS.md). |
| changed lines covered | How many of the PR's changed, executable Python lines ran during the PR side's tests. |
| re-parametrized | A test whose parameter ids changed (renamed cases); the new ids are judged on their own. |
