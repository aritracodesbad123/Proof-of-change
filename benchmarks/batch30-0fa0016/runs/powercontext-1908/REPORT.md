# Reviewer report: oceanbase/powercontext#1908: fix(dify): decouple generated contract from whole OpenAPI hash

Run `powercontext-1908`, tested 2026-10-22 09:09 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 09:10 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** fix(dify): decouple generated contract from whole OpenAPI hash ([oceanbase/powercontext#1908](https://github.com/oceanbase/powercontext/pull/1908)).
- **What we observed:** tests produced no results on one side (collection failed; see pytest logs); probe model-probe-c1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-c2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-c3 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 11.6 GB (of 15.6 GB).
- Setup check: free disk 91.3 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: powercontext python setup install instructions https://github.com/oceanbase/powercontext site:github.com/oceanbase/powercontext
- Query: powercontext python documentation install https://github.com/oceanbase/powercontext site:github.com/oceanbase/powercontext
- Query: powercontext python install requirements https://pypi.org/project/powercontext/ https://github.com/oceanbase/powercontext site:pypi.org
- Source: powercontext · PyPI — https://pypi.org/project/powercontext/
- Source: GitHub - oceanbase/powercontext: Not only memory but a full story · GitHub — https://github.com/oceanbase/powercontext
- Source: Releases · oceanbase/powercontext · GitHub — https://github.com/oceanbase/powercontext/releases
- Source: powercontext/docs/en/docs/integrations/langgraph.md at master · oceanbase/powercontext · GitHub — https://github.com/oceanbase/powercontext/blob/master/docs/en/docs/integrations/langgraph.md
- Source: powercontext/docs/en/docs/how-to/install-and-run.md at master — https://github.com/oceanbase/powercontext/blob/master/docs/en/docs/how-to/install-and-run.md
- Setup plan: the same packages on main and pr.
- Setup plan: pydantic is noted, installed with the project.
- Setup plan: rfc8785 is noted, installed with the project.
- Setup plan: typing-extensions is noted, installed with the project.
- Setup plan: install PyYAML==6.0.3 (listed in requirements-dev.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.11,<4.0, <4.0,>=3.11
- Installed PyYAML 6.0.3 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| P-C1 | After this PR, Dify artifacts will only change when the contract or tool declarations change, not due to unrelated OpenAPI edits. (PR description) | ⚪ **not testable** | probe model-probe-c1 has no observation for this claim | no matching log line |
| P-C2 | The tool's behavior remains the same after this change. (PR description) | ⚪ **not testable** | probe model-probe-c2 has no observation for this claim | no matching log line |
| P-C3 | The generated runtime contract continues to be stored in the repository after this PR. (PR description) | ⚪ **not testable** | probe model-probe-c3 has no observation for this claim | no matching log line |

Citation check (SKIP): no log lines to cite (no tests ran).

## What changed in behavior

Not measured: tests produced no results on one side (collection failed; see pytest logs); probe model-probe-c1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-c2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-c3 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count.

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-probe-c1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe-c1.py`, frozen `ef4160f937f8` at 2026-10-22T03:40:53.189667+00:00): Check presence of openapi_sha256 in generated contract

- P-C1 (PR description): After this PR, Dify artifacts will only change when the contract or tool declarations change, not due to unrelated OpenAPI edits. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-probe-c1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-probe-c1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c1-pr-1.jsonl) «"observation": "probe.error"» |

**model-probe-c2** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe-c2.py`, frozen `e09c2e1325c7` at 2026-10-22T03:40:53.189855+00:00): Hash of generated pc_search.py tool file

- P-C2 (PR description): The tool's behavior remains the same after this change. Expects the covered observations to stay the same.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-probe-c2-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c2-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-probe-c2-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c2-pr-1.jsonl) «"observation": "probe.error"» |

**model-probe-c3** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe-c3.py`, frozen `17d32545b373` at 2026-10-22T03:40:53.189968+00:00): Check that contract.json is generated and non-empty

- P-C3 (PR description): The generated runtime contract continues to be stored in the repository after this PR. Expects the covered observations to stay the same.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-probe-c3-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c3-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-probe-c3-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c3-pr-1.jsonl) «"observation": "probe.error"» |

**diff-api** (diff (auto-derived from base-side code, model-free); informational under baseline full, `diff-probes/diff-api.py`, frozen `ba0429a765f9` at 2026-10-22T03:40:53.193433+00:00): Public functions touched by the PR, called with type-appropriate inputs on both sides.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `integrations.dify.generate_contract.build.import` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ModuleNotFoundError"}` | [probe-diff-api-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-diff-api-main-1.jsonl) «"observation": "integrations.dify.generate_contract.build.import"»<br>[probe-diff-api-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-diff-api-pr-1.jsonl) «"observation": "integrations.dify.generate_contract.build.import"» |

Citation check (PASS): 8 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: NOT MEASURED, record predates the coverage gate.** No coverage run exists for this record; nothing below is a measurement.

Coverage gate (python, confidence lower): coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result).

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `cbbcddc6722f` of the PR against main (source-pair route).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 8 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | tests produced no results on one side (collection failed; see pytest logs); probe model-probe-c1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-c2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-probe-c3 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| 3 alternating runs per side | 🔴 **FAIL** | main 3, PR 3 of 0 | Re-run with the default --runs 3 and look for timeouts in the pytest logs. |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) | Not a measurement: this record is older than the coverage gate. Re-run the PR with the current ops/daily_run.py to measure it. |
| Probes ran on both sides | 🟠 **WARN** | model-probe-c1 main#1; model-probe-c1 pr#1; model-probe-c1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🔴 **FAIL** | main 3, PR 3 of 0 |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) |
| Probes ran on both sides | 🟠 **WARN** | model-probe-c1 main#1; model-probe-c1 pr#1; model-probe-c1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | ⚪ **SKIP** | no log lines to cite (no tests ran) |
| Every probe observation cites its output line | 🟢 **PASS** | 8 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/powercontext-1908 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/oceanbase/powercontext/pull/1908
```

## Evidence links

- [Pull request oceanbase/powercontext#1908](https://github.com/oceanbase/powercontext/pull/1908)
- [record.json](../../ops/runs/2026-10-22-check-0909/powercontext-1908/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0909/powercontext-1908/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0909/powercontext-1908/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0909/powercontext-1908/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0909/powercontext-1908/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0909/powercontext-1908/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0909/powercontext-1908/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0909/powercontext-1908/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0909/powercontext-1908/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0909/powercontext-1908/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0909/powercontext-1908/pytest-pr-3.log)
- [probe-model-probe-c1-main-1.jsonl](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c1-main-1.jsonl)
- [probe-model-probe-c1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c1-pr-1.jsonl)
- [probe-model-probe-c2-main-1.jsonl](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c2-main-1.jsonl)
- [probe-model-probe-c2-pr-1.jsonl](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c2-pr-1.jsonl)
- [probe-model-probe-c3-main-1.jsonl](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c3-main-1.jsonl)
- [probe-model-probe-c3-pr-1.jsonl](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-model-probe-c3-pr-1.jsonl)
- [probe-diff-api-main-1.jsonl](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-diff-api-main-1.jsonl)
- [probe-diff-api-pr-1.jsonl](../../ops/runs/2026-10-22-check-0909/powercontext-1908/probe-diff-api-pr-1.jsonl)

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
