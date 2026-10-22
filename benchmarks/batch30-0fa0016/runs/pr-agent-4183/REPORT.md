# Reviewer report: The-PR-Agent/pr-agent#4183: perf(gitlab): skip project lookup when fetching a merge request

Run `pr_agent-4183`, tested 2026-10-22 07:45 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 07:48 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** perf(gitlab): skip project lookup when fetching a merge request ([The-PR-Agent/pr-agent#4183](https://github.com/The-PR-Agent/pr-agent/pull/4183)).
- **What we observed:** could not verify: setup gap setup.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.9 GB (of 15.6 GB).
- Setup check: free disk 92.1 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: pr-agent python setup install instructions https://github.com/The-PR-Agent/pr-agent site:github.com/The-PR-Agent/pr-agent
- Query: pr-agent python documentation install https://github.com/The-PR-Agent/pr-agent site:github.com/The-PR-Agent/pr-agent
- Query: pr-agent python install requirements https://pypi.org/project/pr-agent/ https://github.com/The-PR-Agent/pr-agent site:pypi.org
- Source: pr-agent · PyPI — https://pypi.org/project/pr-agent/
- Source: pr-agent/docs/docs/installation/github.md at main · The-PR-Agent/pr-agent · GitHub — https://github.com/The-PR-Agent/pr-agent/blob/main/docs/docs/installation/github.md
- Source: pr-agent/AGENTS.md at main · The-PR-Agent/pr-agent · GitHub — https://github.com/The-PR-Agent/pr-agent/blob/main/AGENTS.md
- Source: PR Agent invocation fails due to OpenAI Inference error · Issue #2055 · The-PR-Agent/pr-agent · GitHub — https://github.com/The-PR-Agent/pr-agent/issues/2055
- Source: GitHub - The-PR-Agent/pr-agent: 🚀 PR Agent: The Original Open-Source PR Reviewer. This project is not the Qodo free tier. · GitHub — https://github.com/The-PR-Agent/pr-agent
- Setup plan: the same packages on main and pr.
- Setup plan: aiohttp is noted, installed with the project.
- Setup plan: anthropic is noted, installed with the project.
- Setup plan: certifi is noted, installed with the project.
- Setup plan: dynaconf is noted, installed with the project.
- Setup plan: fastapi is noted, installed with the project.
- Setup plan: GitPython is noted, installed with the project.
- Setup plan: starlette is noted, installed with the project.
- Setup plan: Jinja2 is noted, installed with the project.
- Setup plan: litellm is noted, installed with the project.
- Setup plan: loguru is noted, installed with the project.
- Setup plan: openai is noted, installed with the project.
- Setup plan: PyJWT is noted, installed with the project.
- Setup plan: PyYAML is noted, installed with the project.
- Setup plan: retry is noted, installed with the project.
- Setup plan: starlette-context is noted, installed with the project.
- Setup plan: tiktoken is noted, installed with the project.
- Setup plan: ujson is noted, installed with the project.
- Setup plan: unidiff is noted, installed with the project.
- Setup plan: urllib3 is noted, installed with the project.
- Setup plan: uvicorn is noted, installed with the project.
- Setup plan: tenacity is noted, installed with the project.
- Setup plan: langfuse is noted, installed with the project.
- Setup plan: gunicorn is noted, installed with the project.
- Setup plan: pydantic is noted, installed with the project.
- Setup plan: pydantic-settings is noted, installed with the project.
- Setup plan: html2text is noted, installed with the project.
- Setup plan: opentelemetry-api is noted, installed with the project.
- Setup plan: opentelemetry-sdk is noted, installed with the project.
- Setup plan: opentelemetry-exporter-otlp-proto-http is noted, installed with the project.
- Setup plan: prometheus-client is noted, installed with the project.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.12
- Before rerun: could_not_verify: no test actually ran on either side: 0 tests ran; 0 new test(s) pass, 0 unchanged; 1 test module(s) fail to load on both sides (tests.unittest.test_gitlab_provider), so their tests did not run; test module tests.unittest.test_gitlab_lazy_mr_lookup fails to load on the PR side (0 test(s) no longer run); probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-p2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count
- After rerun: not rerun. could not verify: setup gap setup

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (0 unchanged, 3 runs per side) | [pytest-pr-1.log:33](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-pr-1.log) «2 errors in 1.60s» |
| P-C2 | Avoid fetching GitLab project metadata when a project identifier is already available. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C4 | Eliminates one GitLab API request per merge-request lookup. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C5 | The returned merge request object is unchanged. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C6 | Error handling for merge request lookup is unchanged. (PR description) | ⚪ **not testable** | probe model-p2 has no observation for this claim | no matching log line |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 1 test module(s) fail to load on the PR side only (their tests no longer run), e.g. tests.unittest.test_gitlab_lazy_mr_lookup (0 test(s) on the other side) | [pytest-pr-1.log:33](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-pr-1.log) «2 errors in 1.60s» |

Citation check (WARN): 2 citation(s) verified; 4 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 0 / 0 | - |
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
| Test modules that fail to load on the PR side only (their tests no longer run) | 1 | `tests.unittest.test_gitlab_lazy_mr_lookup (0 test(s) on the other side)` |
| Test modules that fail to load on main only (no baseline for their tests) | 0 | - |
| Test modules that fail to load on both sides (their tests did not run) | 1 | `tests.unittest.test_gitlab_provider` |
| Tests that fail identically on both sides (already broken on main) | 0 | - |

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-p1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-p1.py`, frozen `6b626f5353f4` at 2026-10-22T02:18:07.997525+00:00): Normal case: check project and MR calls, and MR object

- P-C2 (PR description): Avoid fetching GitLab project metadata when a project identifier is already available. Expects the covered observations to differ.
- P-C4 (PR description): Eliminates one GitLab API request per merge-request lookup. Expects the covered observations to differ.
- P-C5 (PR description): The returned merge request object is unchanged. Expects the covered observations to stay the same.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-p1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/probe-model-p1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-p1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/probe-model-p1-pr-1.jsonl) «"observation": "probe.error"» |

**model-p2** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-p2.py`, frozen `4393ccca6af9` at 2026-10-22T02:18:07.997692+00:00): Error cases: check exception types for project not found and MR not found

- P-C6 (PR description): Error handling for merge request lookup is unchanged. Expects the covered observations to stay the same.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-p2-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/probe-model-p2-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-p2-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/probe-model-p2-pr-1.jsonl) «"observation": "probe.error"» |

Citation check (PASS): 4 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (3.7 s run).

Coverage gate (python, confidence normal): 0 of 1 changed executable line(s) ran (0%).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `pr_agent/git_providers/gitlab_provider.py` | 1 | 0 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `e602c4aa8532` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- Changed code was exercised (coverage gate): 0 of 1 changed executable line(s) ran (0%).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 4 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | could not verify: setup gap setup | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| pytest exit codes explained | 🔴 **FAIL** | pytest exit 1; no identical pre-existing failures | Read the pytest logs: PR run 1: 1 failure(s) not seen on main; PR run 2: 1 failure(s) not seen on main |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |
| Every claim cites a real log line | 🟠 **WARN** | 2 citation(s) verified; 4 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🔴 **FAIL** | pytest exit 1; no identical pre-existing failures |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | 0 of 1 changed executable line(s) ran (0%) |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 2 citation(s) verified; 4 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 4 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/pr_agent-4183 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/The-PR-Agent/pr-agent/pull/4183
```

## Evidence links

- [Pull request The-PR-Agent/pr-agent#4183](https://github.com/The-PR-Agent/pr-agent/pull/4183)
- [record.json](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/coverage-pr.json)
- [probe-model-p1-main-1.jsonl](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/probe-model-p1-main-1.jsonl)
- [probe-model-p1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/probe-model-p1-pr-1.jsonl)
- [probe-model-p2-main-1.jsonl](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/probe-model-p2-main-1.jsonl)
- [probe-model-p2-pr-1.jsonl](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/probe-model-p2-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:20](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-main-1.log) «1 error in 0.91s»
- pr run 1 result: [pytest-pr-1.log:33](../../ops/runs/2026-10-22-check-0745/pr_agent-4183/pytest-pr-1.log) «2 errors in 1.60s»

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
