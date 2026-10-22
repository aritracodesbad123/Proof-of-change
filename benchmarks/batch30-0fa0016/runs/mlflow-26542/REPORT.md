# Reviewer report: mlflow/mlflow#26542: Load latest Databricks scorers from the scheduled-scorers REST config so feedback records the scorer version

Run `mlflow-26542`, tested 2026-10-22 01:53 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 02:01 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## 🟠 NEEDS ATTENTION
>
> **Recommended action:** Reject  
> **Confidence:** Medium. The run is trustworthy and found a difference a person should look at. Some checks gave warnings: Probes ran on both sides; Every claim cites a real log line
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Load latest Databricks scorers from the scheduled-scorers REST config so feedback records the scorer version ([mlflow/mlflow#26542](https://github.com/mlflow/mlflow/pull/26542)).
- **What we observed:** 3 test(s) removed on the PR side; 1 test(s) re-parametrized (2 -> 1 ids); 64 test(s) ran on main, 65 on the PR; 6 new test(s) pass, 59 unchanged; probe model-c1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-c2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-c3 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-c4a is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count.
- **What you should do:** Do not approve as is. Read 'What changed in behavior' and decide with the PR author.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.0 GB (of 15.6 GB).
- Setup check: free disk 92.5 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 8 results
- Query: mlflow python setup install instructions https://github.com/mlflow/mlflow site:github.com/mlflow/mlflow
- Query: mlflow python documentation install https://github.com/mlflow/mlflow site:github.com/mlflow/mlflow
- Query: mlflow python install requirements https://pypi.org/project/mlflow/ https://github.com/mlflow/mlflow site:pypi.org
- Source: mlflow-tracing — https://pypi.org/project/mlflow-tracing/
- Source: mlflow — https://pypi.org/project/mlflow/
- Source: mlflow-skinny 2.3.1 — https://pypi.org/project/mlflow-skinny/
- Source: mlflow/CONTRIBUTING.md at master · mlflow/mlflow · GitHub — https://github.com/mlflow/mlflow/blob/master/CONTRIBUTING.md
- Source: GitHub - mlflow/mlflow-export-import · GitHub — https://github.com/mlflow/mlflow-export-import
- Source: [SETUP-BUG] I am facing one Issue while deploying MLFLOW to Azure Web App · Issue #20148 · mlflow/mlflow · GitHub — https://github.com/mlflow/mlflow/issues/20148
- Source: mlflow/CHANGELOG.md at master · mlflow/mlflow · GitHub — https://github.com/mlflow/mlflow/blob/master/CHANGELOG.md
- Source: CLAUDE.md · mlflow/mlflow Wiki · GitHub — https://github.com/mlflow/mlflow/wiki/CLAUDE.md
- Setup plan: the same packages on main and pr.
- Setup plan: Flask-CORS is noted, installed with the project.
- Setup plan: Flask is noted, installed with the project.
- Setup plan: aiohttp is noted, installed with the project.
- Setup plan: alembic is noted, installed with the project.
- Setup plan: anyio is noted, installed with the project.
- Setup plan: cachetools is noted, installed with the project.
- Setup plan: click is noted, installed with the project.
- Setup plan: cloudpickle is noted, installed with the project.
- Setup plan: cryptography is noted, installed with the project.
- Setup plan: databricks-sdk is noted, installed with the project.
- Setup plan: docker is noted, installed with the project.
- Setup plan: fastapi is noted, installed with the project.
- Setup plan: gitpython is noted, installed with the project.
- Setup plan: graphene is noted, installed with the project.
- Setup plan: gunicorn is noted, installed with the project.
- Setup plan: huey is noted, installed with the project.
- Setup plan: importlib_metadata is noted, installed with the project.
- Setup plan: matplotlib is noted, installed with the project.
- Setup plan: numpy is noted, installed with the project.
- Setup plan: opentelemetry-api is noted, installed with the project.
- Setup plan: opentelemetry-proto is noted, installed with the project.
- Setup plan: opentelemetry-sdk is noted, installed with the project.
- Setup plan: packaging is noted, installed with the project.
- Setup plan: pandas is noted, installed with the project.
- Setup plan: protobuf is noted, installed with the project.
- Setup plan: pyarrow is noted, installed with the project.
- Setup plan: pydantic is noted, installed with the project.
- Setup plan: python-dotenv is noted, installed with the project.
- Setup plan: pyyaml is noted, installed with the project.
- Setup plan: requests is noted, installed with the project.
- Setup plan: scikit-learn is noted, installed with the project.
- Setup plan: scipy is noted, installed with the project.
- Setup plan: skops is noted, installed with the project.
- Setup plan: sqlalchemy is noted, installed with the project.
- Setup plan: sqlparse is noted, installed with the project.
- Setup plan: starlette is noted, installed with the project.
- Setup plan: typing-extensions is noted, installed with the project.
- Setup plan: uvicorn is noted, installed with the project.
- Setup plan: waitress is noted, installed with the project.
- Setup plan: install psutil (listed in the test extra) on main and pr.
- Setup plan: install pyspark (listed in the test extra) on main and pr.
- Setup plan: install texttable (listed in the test extra) on main and pr.
- Setup plan: install opentelemetry-exporter-otlp-proto-grpc (listed in the test extra) on main and pr.
- Setup plan: install opentelemetry-exporter-otlp-proto-http (listed in the test extra) on main and pr.
- Setup plan: install toml (listed in requirements.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.10
- Installed psutil 7.2.2 from pyproject (listed in the test extra) on main and pr.
- Installed pyspark 4.2.0 from pyproject (listed in the test extra) on main and pr.
- Installed texttable 1.7.2 from pyproject (listed in the test extra) on main and pr.
- Installed opentelemetry-exporter-otlp-proto-grpc 1.45.1 from pyproject (listed in the test extra) on main and pr.
- Installed opentelemetry-exporter-otlp-proto-http 1.45.1 from pyproject (listed in the test extra) on main and pr.
- Installed toml 0.10.2 from requirements.txt (listed in requirements.txt) on main and pr.

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (59 unchanged, 3 runs per side) | [pytest-pr-1.log:21](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-pr-1.log) «65 passed, 4 warnings in 14.77s» |
| P-C1 | After this PR, get_scorer(name) returns scorer objects that include scorer_version, canonical_resource_name, and canonical_resource_name_type populated from the scheduled-scorers REST config. (PR description) | ⚪ **not testable** | probe model-c1 has no observation for this claim | no matching log line |
| P-C2 | When the server omits sample_rate, the scorer reports STOPPED (rather than defaulting to 1.0), matching the server's treatment of a missing sample_rate as 0 for active scorer counting. (PR description) | ⚪ **not testable** | probe model-c2 has no observation for this claim | no matching log line |
| P-C3 | If the server omits scorer_version (scorer versioning disabled), the returned scorer’s version and resource-name fields remain None, just as before, and no error is raised. (PR description) | ⚪ **not testable** | probe model-c3 has no observation for this claim | no matching log line |
| P-C4a | get_scorer(name) no longer fails when another scorer in the same experiment cannot be deserialized. (PR description) | ⚪ **not testable** | probe model-c4a has no observation for this claim | no matching log line |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 3 test(s) ran on main but are missing on the PR side, e.g. tests.genai.scorers.test_scorer_CRUD::test_databricks_backend_list_and_get_use_databricks_agents | [pytest-main-1.log:21](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-main-1.log) «64 passed, 4 warnings in 15.40s» |

Citation check (WARN): 2 citation(s) verified; 4 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 64 / 65 | - |
| Tests unchanged | 59 | - |
| New tests that pass | 6 | - |
| Tests that pass on main but fail on the PR | 0 | - |
| Tests that are new in the PR and fail | 0 | - |
| Tests that ran on main but are missing on the PR side | 3 | `tests.genai.scorers.test_scorer_CRUD::test_databricks_backend_list_and_get_use_databricks_agents`, `tests.genai.test_genai_import_without_agent_sdk::test_get_scorer_raises_when_agents_not_installed`, `tests.genai.test_genai_import_without_agent_sdk::test_list_scorers_raises_when_agents_not_installed` |
| Tests that changed result in another way (for example passed -> skipped) | 0 | - |
| Tests that gave different results between the 3 runs of the same side (flaky) | 0 | - |
| Tests that fail on main and pass on the PR | 0 | - |
| Tests that are new or changed but did not run because an optional module is missing | 0 | - |
| Tests that were re-parametrized (same test, new parameter ids; not counted as removed) | 1 | `tests.genai.scorers.test_scorer_CRUD::test_databricks_backend_agents_missing_scorer_uses_oss_error (2 -> 1 ids)` |
| Test modules that fail to load on the PR side only (their tests no longer run) | 0 | - |
| Test modules that fail to load on main only (no baseline for their tests) | 0 | - |
| Test modules that fail to load on both sides (their tests did not run) | 0 | - |
| Tests that fail identically on both sides (already broken on main) | 0 | - |

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-c1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-c1.py`, frozen `9de22f9f7e1e` at 2026-10-21T20:25:56.277493+00:00): get_scorer(name)

- P-C1 (PR description): After this PR, get_scorer(name) returns scorer objects that include scorer_version, canonical_resource_name, and canonical_resource_name_type populated from the scheduled-scorers REST config. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-c1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-c1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c1-pr-1.jsonl) «"observation": "probe.error"» |

**model-c2** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-c2.py`, frozen `8be2ef10f5bd` at 2026-10-21T20:25:56.277722+00:00): list_scorers()

- P-C2 (PR description): When the server omits sample_rate, the scorer reports STOPPED (rather than defaulting to 1.0), matching the server's treatment of a missing sample_rate as 0 for active scorer counting. Expects the covered observations to stay the same.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 0}` | [probe-model-c2-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c2-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-c2-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c2-pr-1.jsonl) «"observation": "probe.error"» |

**model-c3** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-c3.py`, frozen `4b16d7670c22` at 2026-10-21T20:25:56.277836+00:00): get_scorer(name)

- P-C3 (PR description): If the server omits scorer_version (scorer versioning disabled), the returned scorer’s version and resource-name fields remain None, just as before, and no error is raised. Expects the covered observations to stay the same.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-c3-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c3-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-c3-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c3-pr-1.jsonl) «"observation": "probe.error"» |

**model-c4a** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-c4a.py`, frozen `3dac11617159` at 2026-10-21T20:25:56.277915+00:00): get_scorer(name)

- P-C4a (PR description): get_scorer(name) no longer fails when another scorer in the same experiment cannot be deserialized. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-c4a-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c4a-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-c4a-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c4a-pr-1.jsonl) «"observation": "probe.error"» |

Citation check (PASS): 8 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (25.0 s run).

Coverage gate (python, confidence normal): 6 of 6 changed executable line(s) ran (100%).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `mlflow/genai/scorers/registry.py` | 6 | 6 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `a8d0cee5738e` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: all runs exited 0.
- Changed code was exercised (coverage gate): 6 of 6 changed executable line(s) ran (100%).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 8 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Probes ran on both sides | 🟠 **WARN** | model-c1 main#1; model-c1 pr#1; model-c1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |
| Every claim cites a real log line | 🟠 **WARN** | 2 citation(s) verified; 4 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |
| Behavior difference found | 🟠 **finding** | 3 test(s) removed on the PR side; 1 test(s) re-parametrized (2 -> 1 ids); 64 test(s) ran on main, 65 on the PR; 6 new test(s) pass, 59 unchanged; probe model-c1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-c2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-c3 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-c4a is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count | This is about the PR, not the run: read the failing tests and their log lines, then decide. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | all runs exited 0 |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | 6 of 6 changed executable line(s) ran (100%) |
| Probes ran on both sides | 🟠 **WARN** | model-c1 main#1; model-c1 pr#1; model-c1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 2 citation(s) verified; 4 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 8 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/mlflow-26542 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/mlflow/mlflow/pull/26542
```

## Evidence links

- [Pull request mlflow/mlflow#26542](https://github.com/mlflow/mlflow/pull/26542)
- [record.json](../../ops/runs/2026-10-22-check-0153/mlflow-26542/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0153/mlflow-26542/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0153/mlflow-26542/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0153/mlflow-26542/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-0153/mlflow-26542/coverage-pr.json)
- [probe-model-c1-main-1.jsonl](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c1-main-1.jsonl)
- [probe-model-c1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c1-pr-1.jsonl)
- [probe-model-c2-main-1.jsonl](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c2-main-1.jsonl)
- [probe-model-c2-pr-1.jsonl](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c2-pr-1.jsonl)
- [probe-model-c3-main-1.jsonl](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c3-main-1.jsonl)
- [probe-model-c3-pr-1.jsonl](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c3-pr-1.jsonl)
- [probe-model-c4a-main-1.jsonl](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c4a-main-1.jsonl)
- [probe-model-c4a-pr-1.jsonl](../../ops/runs/2026-10-22-check-0153/mlflow-26542/probe-model-c4a-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:21](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-main-1.log) «64 passed, 4 warnings in 15.40s»
- pr run 1 result: [pytest-pr-1.log:21](../../ops/runs/2026-10-22-check-0153/mlflow-26542/pytest-pr-1.log) «65 passed, 4 warnings in 14.77s»

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
