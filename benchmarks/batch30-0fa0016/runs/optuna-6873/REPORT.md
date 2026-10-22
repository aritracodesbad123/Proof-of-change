# Reviewer report: optuna/optuna#6873: Avoid All-NaN RuntimeWarning in percentile pruner best-value lookup

Run `optuna-6873`, tested 2026-10-22 07:54 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 09:04 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Avoid All-NaN RuntimeWarning in percentile pruner best-value lookup ([optuna/optuna#6873](https://github.com/optuna/optuna/pull/6873)).
- **What we observed:** not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; docstring-only change (AST equal after blanking docstrings); behaviour claims hold by construction.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.0 GB (of 15.6 GB).
- Setup check: free disk 91.6 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 8 results
- Query: optuna python setup install instructions https://github.com/optuna/optuna site:github.com/optuna/optuna
- Query: optuna python documentation install https://github.com/optuna/optuna site:github.com/optuna/optuna
- Query: optuna python install requirements https://pypi.org/project/optuna/ https://github.com/optuna/optuna site:pypi.org
- Source: optuna — https://pypi.org/project/optuna/
- Source: optuna-integration — https://pypi.org/project/optuna-integration/
- Source: v4.0.0 · optuna/optuna · Discussion #5656 · GitHub — https://github.com/optuna/optuna/discussions/5656
- Source: Releases · optuna/optuna · GitHub — https://github.com/optuna/optuna/releases
- Source: GitHub - optuna/optuna-examples: Examples for https://github.com/optuna/optuna · GitHub — https://github.com/optuna/optuna-examples
- Source: GitHub - optuna/optuna-integration: Extended functionalities for Optuna in combination with third-party libraries. · GitHub — https://github.com/optuna/optuna-integration
- Source: GitHub - optuna/optuna: A hyperparameter optimization framework · GitHub — https://github.com/optuna/optuna
- Source: GitHub - optuna/optuna-dashboard: Real-time Web Dashboard for Optuna. · GitHub — https://github.com/optuna/optuna-dashboard
- Setup plan: the same packages on main and pr.
- Setup plan: alembic is noted, installed with the project.
- Setup plan: colorlog is noted, installed with the project.
- Setup plan: numpy is noted, installed with the project.
- Setup plan: packaging is noted, installed with the project.
- Setup plan: sqlalchemy is noted, installed with the project.
- Setup plan: tqdm is noted, installed with the project.
- Setup plan: PyYAML is noted, installed with the project.
- Setup plan: install fakeredis[lua] (listed in the test extra) on main and pr.
- Setup plan: install moto (listed in the test extra) on main and pr.
- Setup plan: install plotly (listed in the test extra) on main and pr.
- Setup plan: install pytest (listed in the test extra) on main and pr.
- Setup plan: install pytest-xdist (listed in the test extra) on main and pr.
- Setup plan: install scipy>=1.9.2 (listed in the test extra) on main and pr.
- Setup plan: install torch (listed in the test extra) on main and pr.
- Setup plan: install greenlet (listed in the test extra) on main and pr.
- Setup plan: install grpcio (listed in the test extra) on main and pr.
- Setup plan: install protobuf>=5.28.1 (listed in the test extra) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.9
- Installed fakeredis 2.40.0 from pyproject (listed in the test extra) on main and pr.
- Installed moto 5.2.4 from pyproject (listed in the test extra) on main and pr.
- Installed plotly 7.1.0 from pyproject (listed in the test extra) on main and pr.
- Installed pytest 9.1.1 from pyproject (listed in the test extra) on main and pr.
- Installed pytest-xdist 3.8.0 from pyproject (listed in the test extra) on main and pr.
- Installed scipy 1.18.1 from pyproject (listed in the test extra) on main and pr.
- Installed torch 2.14.1 from pyproject (listed in the test extra) on main and pr.
- Installed greenlet 3.5.6 from pyproject (listed in the test extra) on main and pr.
- Installed grpcio 1.84.0 from pyproject (listed in the test extra) on main and pr.
- Installed protobuf 7.36.2 from pyproject (listed in the test extra) on main and pr.

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C1 | Avoid All-NaN RuntimeWarning in percentile pruner best-value lookup (PR title) | ⚪ **not testable** | claims are read out of the PR description only by model-written probes (--model-provider, see Probes); the tests below check behavior | [pytest-pr-1.log:7](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-pr-1.log) «11 passed in 1.31s» |
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (11 unchanged, 3 runs per side) | [pytest-pr-1.log:7](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-pr-1.log) «11 passed in 1.31s» |

Citation check (PASS): 2 citation(s), every one re-read from its log file and matched.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 11 / 11 | - |
| Tests unchanged | 11 | - |
| New tests that pass | 0 | - |
| Tests that pass on main but fail on the PR | 0 | - |
| Tests that are new in the PR and fail | 0 | - |
| Tests that ran on main but are missing on the PR side | 0 | - |
| Tests that changed result in another way (for example passed -> skipped) | 0 | - |
| Tests that gave different results between the 3 runs of the same side (flaky) | 0 | - |
| Tests that fail on main and pass on the PR | 0 | - |
| Tests that are new or changed but did not run because an optional module is missing | 0 | - |
| Tests that were re-parametrized (same test, new parameter ids; not counted as removed) | 0 | - |
| Test modules that fail to load on the PR side only (their tests no longer run) | 0 | - |
| Test modules that fail to load on main only (no baseline for their tests) | 0 | - |
| Test modules that fail to load on both sides (their tests did not run) | 0 | - |
| Tests that fail identically on both sides (already broken on main) | 0 | - |

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-p1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-p1.py`, frozen `5b92d8e8f451` at 2026-10-22T03:32:51.934816+00:00): Tests _get_best_intermediate_result_over_steps for all-NaN, mixed, and empty cases.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 0}` | [probe-model-p1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0754/optuna-6873/probe-model-p1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-p1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0754/optuna-6873/probe-model-p1-pr-1.jsonl) «"observation": "probe.error"» |

Citation check (PASS): 2 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (2.6 s run).

Coverage gate (python, confidence normal): the changed Python lines are not executable (comments, docstrings, blank lines).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `optuna/pruners/_percentile.py` | 0 | 0 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `83a36def362a` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: all runs exited 0.
- Changed code was exercised (coverage gate): the changed Python lines are not executable (comments, docstrings, blank lines).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every claim cites a real log line: 2 citation(s), every one re-read from its log file and matched.
- Every probe observation cites its output line: 2 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; docstring-only change (AST equal after blanking docstrings); behaviour claims hold by construction | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | all runs exited 0 |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | the changed Python lines are not executable (comments, docstrings, blank lines) |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟢 **PASS** | 2 citation(s), every one re-read from its log file and matched |
| Every probe observation cites its output line | 🟢 **PASS** | 2 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/optuna-6873 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/optuna/optuna/pull/6873
```

## Evidence links

- [Pull request optuna/optuna#6873](https://github.com/optuna/optuna/pull/6873)
- [record.json](../../ops/runs/2026-10-22-check-0754/optuna-6873/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0754/optuna-6873/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0754/optuna-6873/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0754/optuna-6873/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0754/optuna-6873/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-0754/optuna-6873/coverage-pr.json)
- [probe-model-p1-main-1.jsonl](../../ops/runs/2026-10-22-check-0754/optuna-6873/probe-model-p1-main-1.jsonl)
- [probe-model-p1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0754/optuna-6873/probe-model-p1-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:7](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-main-1.log) «11 passed in 1.13s»
- pr run 1 result: [pytest-pr-1.log:7](../../ops/runs/2026-10-22-check-0754/optuna-6873/pytest-pr-1.log) «11 passed in 1.31s»

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
