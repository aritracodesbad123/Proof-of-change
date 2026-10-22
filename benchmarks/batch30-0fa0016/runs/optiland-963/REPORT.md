# Reviewer report: optiland/optiland#963: Remove the duplicate separator beside navigation

Run `optiland-963`, tested 2026-10-22 09:11 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 10:21 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Remove the duplicate separator beside navigation ([optiland/optiland#963](https://github.com/optiland/optiland/pull/963)).
- **What we observed:** could not verify: setup gap setup.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 11.3 GB (of 15.6 GB).
- Setup check: free disk 91.2 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: optiland python setup install instructions https://github.com/optiland/optiland site:github.com/optiland/optiland
- Query: optiland python documentation install https://github.com/optiland/optiland site:github.com/optiland/optiland
- Query: optiland python install requirements https://pypi.org/project/optiland/ https://github.com/optiland/optiland site:pypi.org
- Source: optiland · PyPI — https://pypi.org/project/optiland/
- Source: GitHub - optiland/optiland: Comprehensive optical design, optimization, and analysis in Python, including GPU-accelerated and differentiable ray tracing via PyTorch. · GitHub — https://github.com/optiland/optiland
- Source: optiland/CONTRIBUTING.md at master · optiland/optiland · GitHub — https://github.com/optiland/optiland/blob/master/CONTRIBUTING.md
- Source: Ray aiming Issues · Issue #654 · optiland/optiland · GitHub — https://github.com/optiland/optiland/issues/654
- Source: No Wayland support? · Issue #556 · optiland/optiland · GitHub — https://github.com/optiland/optiland/issues/556
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
- Before rerun: could_not_verify: test module tests.gui.test_sidebar_separator fails to load on the PR side (0 test(s) no longer run): 7083 test(s) ran on main, 7083 on the PR; 0 new test(s) pass, 7513 unchanged (510 of them skipped on both sides); 80 test failure(s) pre-existing and identical on both sides; 25 test module(s) fail to load on both sides (tests.gui.test_analysis_jobs_process, tests.gui.test_analysis_panel, tests.gui.test_checkbox_indicators (+22)), so their tests did not run; test module tests.gui.test_sidebar_separator fails to load on the PR side (0 test(s) no longer run); probe model-probe1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe3 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count
- After rerun: not rerun. could not verify: setup gap setup

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (7593 unchanged, 3 runs per side) | [pytest-pr-1.log:2580](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-pr-1.log) «1 failed, 7003 passed, 509 skipped, 1 xfailed, 1111 warnings, 105 errors, 28 subtests passed in 155.07s (0:02:35)» |
| P-C1 | After the change, Qt docks fill the workspace (no unused empty central widget reserving space). (PR description) | ⚪ **not testable** | probe model-probe1 has no observation for this claim | no matching log line |
| P-C2 | After the change, there is exactly one native draggable separator beside navigation (instead of adjacent separators). (PR description) | ⚪ **not testable** | probe model-probe2 has no observation for this claim | no matching log line |
| P-C3 | Existing panel construction, initial plots and native layout persistence remain unchanged after the change. (PR description) | ⚪ **not testable** | probe model-probe3 has no observation for this claim | no matching log line |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 1 test module(s) fail to load on the PR side only (their tests no longer run), e.g. tests.gui.test_sidebar_separator (0 test(s) on the other side) | [pytest-pr-1.log:2580](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-pr-1.log) «1 failed, 7003 passed, 509 skipped, 1 xfailed, 1111 warnings, 105 errors, 28 subtests passed in 155.07s (0:02:35)» |

Citation check (WARN): 2 citation(s) verified; 3 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 7083 / 7083 | - |
| Tests unchanged | 7593 | - |
| New tests that pass | 0 | - |
| Tests that pass on main but fail on the PR | 0 | - |
| Tests that are new in the PR and fail | 0 | - |
| Tests that ran on main but are missing on the PR side | 0 | - |
| Tests that changed result in another way (for example passed -> skipped) | 0 | - |
| Tests that gave different results between the 3 runs of the same side (flaky) | 0 | - |
| Tests that fail on main and pass on the PR | 0 | - |
| Tests that are new or changed but did not run because an optional module is missing | 0 | - |
| Tests that were re-parametrized (same test, new parameter ids; not counted as removed) | 0 | - |
| Test modules that fail to load on the PR side only (their tests no longer run) | 1 | `tests.gui.test_sidebar_separator (0 test(s) on the other side)` |
| Test modules that fail to load on main only (no baseline for their tests) | 0 | - |
| Test modules that fail to load on both sides (their tests did not run) | 25 | `tests.gui.test_analysis_jobs_process`, `tests.gui.test_analysis_panel`, `tests.gui.test_checkbox_indicators`, `tests.gui.test_document_producers`, `tests.gui.test_document_refresh` |
| Tests that fail identically on both sides (already broken on main) | 80 | `tests.gui.test_analysis_runner::test_batch_closed_service_reports_first_failure_and_cancels_rest`, `tests.gui.test_analysis_runner::test_batch_waiting_for_queue_can_be_stopped_without_later_submission`, `tests.gui.test_analysis_runner::test_explicit_rerun_supersedes_unsent_batch_entry`, `tests.gui.test_analysis_runner::test_numerical_failure_with_transport_words_does_not_stop_batch`, `tests.gui.test_analysis_runner::test_registry_and_workload_validation_before_snapshot` |

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-probe1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe1.py`, frozen `1d1cd072071e` at 2026-10-22T03:42:48.171877+00:00): Check central widget placeholder

- P-C1 (PR description): After the change, Qt docks fill the workspace (no unused empty central widget reserving space). Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-probe1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe1-pr-1.jsonl) «"observation": "probe.error"» |

**model-probe2** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe2.py`, frozen `905e279722bb` at 2026-10-22T03:42:48.172035+00:00): Count docks in left area

- P-C2 (PR description): After the change, there is exactly one native draggable separator beside navigation (instead of adjacent separators). Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-probe2-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe2-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-probe2-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe2-pr-1.jsonl) «"observation": "probe.error"» |

**model-probe3** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe3.py`, frozen `9902e9d7af14` at 2026-10-22T03:42:48.172136+00:00): Check analysis panel existence

- P-C3 (PR description): Existing panel construction, initial plots and native layout persistence remain unchanged after the change. Expects the covered observations to stay the same.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-probe3-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe3-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-probe3-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe3-pr-1.jsonl) «"observation": "probe.error"» |

Citation check (PASS): 6 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: NOT MEASURED** (coverage run produced no data (exit 1); see coverage-pytest.log).

Coverage gate (python, confidence lower): coverage of the changed Python lines was NOT MEASURED (coverage run produced no data (exit 1); see coverage-pytest.log).

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## Missing optional modules

- 316 unchanged test(s) skipped on both sides because `torch` is not installed (coverage gap, verdict unaffected).
- 15 unchanged test(s) skipped on both sides because `PyTorch` is not installed (coverage gap, verdict unaffected).

## What went right

- Tested `9b8ce0cd1a8a` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 6 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | could not verify: setup gap setup | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| pytest exit codes explained | 🔴 **FAIL** | pytest exit 1; 80 failure(s)/error(s) pre-existing and identical on both sides | Read the pytest logs: PR run 1: 1 failure(s) not seen on main; PR run 2: 1 failure(s) not seen on main |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (coverage run produced no data (exit 1); see coverage-pytest.log) | The coverage run did not produce data (see coverage.why); run the check again. |
| Optional modules installed | 🟠 **WARN** | unchanged tests skipped on both sides: torch (316), PyTorch (15) | Add the module(s) to optional_test_deps for this library in ops/daily_run.py and run again. |
| Probes ran on both sides | 🟠 **WARN** | model-probe1 main#1; model-probe1 pr#1; model-probe1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |
| Every claim cites a real log line | 🟠 **WARN** | 2 citation(s) verified; 3 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🔴 **FAIL** | pytest exit 1; 80 failure(s)/error(s) pre-existing and identical on both sides |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (coverage run produced no data (exit 1); see coverage-pytest.log) |
| Optional modules installed | 🟠 **WARN** | unchanged tests skipped on both sides: torch (316), PyTorch (15) |
| Probes ran on both sides | 🟠 **WARN** | model-probe1 main#1; model-probe1 pr#1; model-probe1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 2 citation(s) verified; 3 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 6 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/optiland-963 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/optiland/optiland/pull/963
```

## Evidence links

- [Pull request optiland/optiland#963](https://github.com/optiland/optiland/pull/963)
- [record.json](../../ops/runs/2026-10-22-check-0911/optiland-963/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0911/optiland-963/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0911/optiland-963/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0911/optiland-963/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0911/optiland-963/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0911/optiland-963/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0911/optiland-963/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0911/optiland-963/coverage-pytest.log)
- [probe-model-probe1-main-1.jsonl](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe1-main-1.jsonl)
- [probe-model-probe1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe1-pr-1.jsonl)
- [probe-model-probe2-main-1.jsonl](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe2-main-1.jsonl)
- [probe-model-probe2-pr-1.jsonl](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe2-pr-1.jsonl)
- [probe-model-probe3-main-1.jsonl](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe3-main-1.jsonl)
- [probe-model-probe3-pr-1.jsonl](../../ops/runs/2026-10-22-check-0911/optiland-963/probe-model-probe3-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:2569](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-main-1.log) «1 failed, 7003 passed, 509 skipped, 1 xfailed, 1111 warnings, 104 errors, 28 subtests passed in 125.32s (0:02:05)»
- pr run 1 result: [pytest-pr-1.log:2580](../../ops/runs/2026-10-22-check-0911/optiland-963/pytest-pr-1.log) «1 failed, 7003 passed, 509 skipped, 1 xfailed, 1111 warnings, 105 errors, 28 subtests passed in 155.07s (0:02:35)»

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
