# Reviewer report: optuna/optuna#6873: Avoid All-NaN RuntimeWarning in percentile pruner best-value lookup

Run `optuna-6873`, tested 2026-10-22 23:28 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `527dff7b74cbdb43d4c87c94ca5fc45de85ae08d`. Report generated 2026-10-22 23:33 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Avoid All-NaN RuntimeWarning in percentile pruner best-value lookup ([optuna/optuna#6873](https://github.com/optuna/optuna/pull/6873)).
- **What we observed:** unverified behaviour claim: "The returned value is identical to before (NaN), so pruning behavior is unchanged." (+1 more); needs a probe (11 test(s) ran on main, 11 on the PR; 0 new test(s) pass, 11 unchanged; probe model-probe-c2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-c3 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change).
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 7.3 GB (of 15.6 GB).
- Setup check: free disk 40.1 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 8 results
- Query: optuna python setup install instructions https://github.com/optuna/optuna site:github.com/optuna/optuna
- Query: optuna python documentation install https://github.com/optuna/optuna site:github.com/optuna/optuna
- Query: optuna python install requirements https://pypi.org/project/optuna/ https://github.com/optuna/optuna site:pypi.org
- Source: optuna — https://pypi.org/project/optuna/
- Source: optuna-integration — https://pypi.org/project/optuna-integration/
- Source: optuna/CONTRIBUTING.md at master · optuna/optuna · GitHub — https://github.com/optuna/optuna/blob/master/CONTRIBUTING.md
- Source: v4.0.0 · optuna/optuna · Discussion #5656 · GitHub — https://github.com/optuna/optuna/discussions/5656
- Source: RuntimeError: The runtime optuna version 2.8.0 is no longer compatible with the table schema (set up by optuna 2.8.0). Please try updating optuna to the latest version by `$ pip install -U optuna`. · Issue #2812 · optuna/optuna · GitHub — https://github.com/optuna/optuna/issues/2812
- Source: GitHub - optuna/optuna-integration: Extended functionalities for Optuna in combination with third-party libraries. · GitHub — https://github.com/optuna/optuna-integration
- Source: GitHub - optuna/optuna at dagshub.com · GitHub — https://github.com/optuna/optuna?ref=dagshub.com
- Source: GitHub - optuna/optuna: A hyperparameter optimization framework · GitHub — https://github.com/optuna/optuna
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
- Setup plan: install mypy (listed in a dependency group) on main and pr.
- Setup plan: install mypy_boto3_s3 (listed in a dependency group) on main and pr.
- Setup plan: install ruff (listed in a dependency group) on main and pr.
- Setup plan: install scipy-stubs; python_version>='3.10' (listed in a dependency group) on main and pr.
- Setup plan: install types-PyYAML (listed in a dependency group) on main and pr.
- Setup plan: install types-redis (listed in a dependency group) on main and pr.
- Setup plan: install types-setuptools (listed in a dependency group) on main and pr.
- Setup plan: install types-tqdm (listed in a dependency group) on main and pr.
- Setup plan: install typing_extensions>=3.10.0.0 (listed in a dependency group) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.9
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C1 | Avoid All-NaN RuntimeWarning in percentile pruner best-value lookup (PR title) | ⚪ **not testable** | claims are read out of the PR description only by model-written probes (--model-provider, see Probes); the tests below check behavior | [pytest-pr-1.log:6](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-pr-1.log) «11 passed in 0.90s» |
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (11 unchanged, 3 runs per side) | [pytest-pr-1.log:6](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-pr-1.log) «11 passed in 0.90s» |

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

Probe test settings: read from main's checkout (pyproject.toml), the same on both sides. Variables: none.

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-probe-c2** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe-c2.py`, frozen `82fd98e135fd` at 2026-10-22T18:00:03.624077+00:00): Probe for claim C2: all-NaN input returns NaN

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-probe-c2-main-1.jsonl:1](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/probe-model-probe-c2-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-probe-c2-pr-1.jsonl:1](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/probe-model-probe-c2-pr-1.jsonl) «"observation": "probe.error"» |

**model-probe-c3** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe-c3.py`, frozen `3d96536387ca` at 2026-10-22T18:00:03.624212+00:00): Probe for claim C3: empty input raises ValueError

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `exception` | - | 🟢 **same on both sides** | same on both sides: `"ValueError"` | [probe-model-probe-c3-main-1.jsonl:1](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/probe-model-probe-c3-main-1.jsonl) «"observation": "exception"»<br>[probe-model-probe-c3-pr-1.jsonl:1](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/probe-model-probe-c3-pr-1.jsonl) «"observation": "exception"» |

Citation check (PASS): 4 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (4.8 s run).

Coverage gate (python, confidence normal): 2 of 2 changed executable line(s) ran (100%).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `optuna/pruners/_percentile.py` | 2 | 2 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `83a36def362a` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: all runs exited 0.
- Changed code was exercised (coverage gate): 2 of 2 changed executable line(s) ran (100%).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every claim cites a real log line: 2 citation(s), every one re-read from its log file and matched.
- Every probe observation cites its output line: 4 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | unverified behaviour claim: "The returned value is identical to before (NaN), so pruning behavior is unchanged." (+1 more); needs a probe (11 test(s) ran on main, 11 on the PR; 0 new test(s) pass, 11 unchanged; probe model-probe-c2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-c3 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change) | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| Probes ran on both sides | 🟠 **WARN** | model-probe-c2 main#1; model-probe-c2 pr#1; model-probe-c2 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | all runs exited 0 |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | 2 of 2 changed executable line(s) ran (100%) |
| Probes ran on both sides | 🟠 **WARN** | model-probe-c2 main#1; model-probe-c2 pr#1; model-probe-c2 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟢 **PASS** | 2 citation(s), every one re-read from its log file and matched |
| Every probe observation cites its output line | 🟢 **PASS** | 4 citation(s), every one re-read from its log file and matched |

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
- [record.json](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/record.json)
- [pr.diff](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pr.diff)
- [git.log](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/git.log)
- [pytest-main-1.log](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-main-1.log)
- [pytest-pr-1.log](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-pr-1.log)
- [pytest-main-2.log](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-main-2.log)
- [pytest-pr-2.log](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-pr-2.log)
- [pytest-main-3.log](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-main-3.log)
- [pytest-pr-3.log](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-pr-3.log)
- [junit-main-1.xml](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/junit-main-1.xml)
- [junit-pr-1.xml](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/junit-pr-1.xml)
- [coverage-pytest.log](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/coverage-pytest.log)
- [coverage-pr.json](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/coverage-pr.json)
- [probe-model-probe-c2-main-1.jsonl](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/probe-model-probe-c2-main-1.jsonl)
- [probe-model-probe-c2-pr-1.jsonl](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/probe-model-probe-c2-pr-1.jsonl)
- [probe-model-probe-c3-main-1.jsonl](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/probe-model-probe-c3-main-1.jsonl)
- [probe-model-probe-c3-pr-1.jsonl](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/probe-model-probe-c3-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:6](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-main-1.log) «11 passed in 0.86s»
- pr run 1 result: [pytest-pr-1.log:6](../../../../ops/runs/2026-10-22-check-232846-pr6873/optuna-6873/pytest-pr-1.log) «11 passed in 0.90s»

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
