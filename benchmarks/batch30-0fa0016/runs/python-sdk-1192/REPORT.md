# Reviewer report: dapr/python-sdk#1192: Fix convert_to_dapr_duration double-counting sub-second time

Run `python_sdk-1192`, tested 2026-10-22 07:51 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 07:53 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Fix convert_to_dapr_duration double-counting sub-second time ([dapr/python-sdk#1192](https://github.com/dapr/python-sdk/pull/1192)).
- **What we observed:** not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 9 test(s) ran on main, 10 on the PR; 1 new test(s) pass, 9 unchanged; probe model-probe1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.1 GB (of 15.6 GB).
- Setup check: free disk 91.8 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 2 results
- Query: python-sdk python setup install instructions https://github.com/dapr/python-sdk site:github.com/dapr/python-sdk
- Query: python-sdk python documentation install https://github.com/dapr/python-sdk site:github.com/dapr/python-sdk
- Query: python-sdk python install requirements https://pypi.org/project/python-sdk/ https://github.com/dapr/python-sdk site:pypi.org
- Source: GitHub - dapr/python-sdk: Dapr SDK for Python · GitHub — https://github.com/dapr/python-sdk
- Source: Can not find service @ example "invoke-simple" · Issue #146 — https://github.com/dapr/python-sdk/issues/146
- Setup plan: the same packages on main and pr.
- Setup plan: protobuf is noted, installed with the project.
- Setup plan: grpcio is noted, installed with the project.
- Setup plan: grpcio-status is noted, installed with the project.
- Setup plan: aiohttp is noted, installed with the project.
- Setup plan: python-dateutil is noted, installed with the project.
- Setup plan: typing-extensions is noted, installed with the project.
- Setup plan: install mechanical-markdown~=0.8.0 (listed in the tests extra) on main and pr.
- Setup plan: install langchain-ollama>=1.0.1,<1.2.0 (listed in the tests extra) on main and pr.
- Setup plan: install dapr[grpc] >= 1.19.0.dev (listed in requirements.txt) on main and pr.
- Setup plan: install langchain-core>=1.0.7 (listed in requirements.txt) on main and pr.
- Setup plan: install langgraph>=1.0.3 (listed in requirements.txt) on main and pr.
- Setup plan: install mcp (listed in requirements.txt) on main and pr.
- Setup plan: install pydantic >= 2.0 (listed in requirements.txt) on main and pr.
- Setup plan: install opentelemetry-sdk (listed in requirements.txt) on main and pr.
- Setup plan: install opentelemetry-instrumentation-grpc (listed in requirements.txt) on main and pr.
- Setup plan: install opentelemetry-exporter-zipkin (listed in requirements.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.10
- Installed mechanical-markdown 0.8.0 from pyproject (listed in the tests extra) on main and pr.
- Installed langchain-ollama 1.1.0 from pyproject (listed in the tests extra) on main and pr.
- Installed dapr 1.19.0.dev from requirements.txt (listed in requirements.txt) on main and pr.
- Installed langchain-core 1.6.13 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed langgraph 1.2.16 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed mcp 2.1.1 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed pydantic 2.13.5 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed opentelemetry-sdk 1.44.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed opentelemetry-instrumentation-grpc 0.65b0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed opentelemetry-exporter-zipkin 1.11.1 from requirements.txt (listed in requirements.txt) on main and pr.

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C1 | Fix convert_to_dapr_duration double-counting sub-second time (PR title) | ⚪ **not testable** | claims are read out of the PR description only by model-written probes (--model-provider, see Probes); the tests below check behavior | [pytest-pr-1.log:7](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-pr-1.log) «10 passed in 1.53s» |
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (9 unchanged, 3 runs per side) | [pytest-pr-1.log:7](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-pr-1.log) «10 passed in 1.53s» |

Citation check (PASS): 2 citation(s), every one re-read from its log file and matched.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 9 / 10 | - |
| Tests unchanged | 9 | - |
| New tests that pass | 1 | - |
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

**model-probe1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe1.py`, frozen `63337c4c5127` at 2026-10-22T02:23:03.249105+00:00): model-written probe of the changed files (no description given)

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 0}` | [probe-model-probe1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-model-probe1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-model-probe1-pr-1.jsonl) «"observation": "probe.error"» |

**diff-api** (diff (auto-derived from base-side code, model-free); informational under baseline full, `diff-probes/diff-api.py`, frozen `b7133b5954cc` at 2026-10-22T02:23:03.250463+00:00): Public functions touched by the PR, called with type-appropriate inputs on both sides.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `dapr.serializers.util.convert_to_dapr_duration.input0` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input0"»<br>[probe-diff-api-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input0"» |
| `dapr.serializers.util.convert_to_dapr_duration.input1` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:2](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input1"»<br>[probe-diff-api-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input1"» |
| `dapr.serializers.util.convert_to_dapr_duration.input10` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:3](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input10"»<br>[probe-diff-api-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input10"» |
| `dapr.serializers.util.convert_to_dapr_duration.input11` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:4](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input11"»<br>[probe-diff-api-pr-1.jsonl:4](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input11"» |
| `dapr.serializers.util.convert_to_dapr_duration.input2` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:5](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input2"»<br>[probe-diff-api-pr-1.jsonl:5](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input2"» |
| `dapr.serializers.util.convert_to_dapr_duration.input3` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:6](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input3"»<br>[probe-diff-api-pr-1.jsonl:6](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input3"» |
| `dapr.serializers.util.convert_to_dapr_duration.input4` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:7](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input4"»<br>[probe-diff-api-pr-1.jsonl:7](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input4"» |
| `dapr.serializers.util.convert_to_dapr_duration.input5` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:8](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input5"»<br>[probe-diff-api-pr-1.jsonl:8](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input5"» |
| `dapr.serializers.util.convert_to_dapr_duration.input6` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:9](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input6"»<br>[probe-diff-api-pr-1.jsonl:9](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input6"» |
| `dapr.serializers.util.convert_to_dapr_duration.input7` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:10](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input7"»<br>[probe-diff-api-pr-1.jsonl:10](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input7"» |
| `dapr.serializers.util.convert_to_dapr_duration.input8` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:11](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input8"»<br>[probe-diff-api-pr-1.jsonl:11](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input8"» |
| `dapr.serializers.util.convert_to_dapr_duration.input9` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:12](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input9"»<br>[probe-diff-api-pr-1.jsonl:12](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl) «"observation": "dapr.serializers.util.convert_to_dapr_duration.input9"» |

Citation check (PASS): 26 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (3.4 s run).

Coverage gate (python, confidence normal): 1 of 1 changed executable line(s) ran (100%).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `dapr/serializers/util.py` | 1 | 1 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `df406e5f0e28` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: all runs exited 0.
- Changed code was exercised (coverage gate): 1 of 1 changed executable line(s) ran (100%).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every claim cites a real log line: 2 citation(s), every one re-read from its log file and matched.
- Every probe observation cites its output line: 26 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | not verified: no AI-written probe ran any changed line, so the change itself was not exercised by a probe; 9 test(s) ran on main, 10 on the PR; 1 new test(s) pass, 9 unchanged; probe model-probe1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| Probes ran on both sides | 🟠 **WARN** | model-probe1 main#1; model-probe1 pr#1; model-probe1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | all runs exited 0 |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | 1 of 1 changed executable line(s) ran (100%) |
| Probes ran on both sides | 🟠 **WARN** | model-probe1 main#1; model-probe1 pr#1; model-probe1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟢 **PASS** | 2 citation(s), every one re-read from its log file and matched |
| Every probe observation cites its output line | 🟢 **PASS** | 26 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/python_sdk-1192 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/dapr/python-sdk/pull/1192
```

## Evidence links

- [Pull request dapr/python-sdk#1192](https://github.com/dapr/python-sdk/pull/1192)
- [record.json](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/coverage-pr.json)
- [probe-model-probe1-main-1.jsonl](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-model-probe1-main-1.jsonl)
- [probe-model-probe1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-model-probe1-pr-1.jsonl)
- [probe-diff-api-main-1.jsonl](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-main-1.jsonl)
- [probe-diff-api-pr-1.jsonl](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/probe-diff-api-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:7](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-main-1.log) «9 passed in 1.61s»
- pr run 1 result: [pytest-pr-1.log:7](../../ops/runs/2026-10-22-check-0751/python_sdk-1192/pytest-pr-1.log) «10 passed in 1.53s»

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
