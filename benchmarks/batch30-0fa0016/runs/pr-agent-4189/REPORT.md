# Reviewer report: The-PR-Agent/pr-agent#4189: perf(similar_issue): batch embeddings before individual retries

Run `pr_agent-4189`, tested 2026-10-22 01:18 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 01:21 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## 🟠 NEEDS ATTENTION
>
> **Recommended action:** Reject  
> **Confidence:** Medium. The run is trustworthy and found a difference a person should look at. Some checks gave warnings: Every claim cites a real log line
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** perf(similar_issue): batch embeddings before individual retries ([The-PR-Agent/pr-agent#4189](https://github.com/The-PR-Agent/pr-agent/pull/4189)).
- **What we observed:** probe: 4 observation(s) need attention: tc2_call_count does not differ although the claim says it does (C2); tc2_outcome does not differ although the claim says it does (C2); tc4_call_count does not differ although the claim says it does (C2); tc4_outcome does not differ although the claim says it does (C2); probe: claim(s) C1, C2 proven; tests: 43 test(s) ran on main, 47 on the PR; 4 new test(s) pass, 43 unchanged.
- **What you should do:** Do not approve as is. Read 'What changed in behavior' and decide with the PR author.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 5.9 GB (of 15.6 GB).
- Setup check: free disk 92.9 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 4 results
- Query: pr-agent python setup install instructions https://github.com/The-PR-Agent/pr-agent site:github.com/The-PR-Agent/pr-agent
- Query: pr-agent python documentation install https://github.com/The-PR-Agent/pr-agent site:github.com/The-PR-Agent/pr-agent
- Query: pr-agent python install requirements https://pypi.org/project/pr-agent/ https://github.com/The-PR-Agent/pr-agent site:pypi.org
- Source: pr-agent/docs/docs/installation/github.md at main · The-PR-Agent/pr-agent · GitHub — https://github.com/The-PR-Agent/pr-agent/blob/main/docs/docs/installation/github.md
- Source: pr-agent/AGENTS.md at main · The-PR-Agent/pr-agent · GitHub — https://github.com/The-PR-Agent/pr-agent/blob/main/AGENTS.md
- Source: Releases · The-PR-Agent/pr-agent · GitHub — https://github.com/the-pr-agent/pr-agent/releases
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

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (43 unchanged, 3 runs per side) | [pytest-pr-1.log:16](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pytest-pr-1.log) «47 passed, 4 warnings in 2.10s» |
| P-C1 | When a bulk embedding request succeeds, the system uses a single request (fast path unchanged). (PR description) | 🟢 **proven** | probe model-probe1, tc1_call_count: same on both sides: `1` | [probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc1_call_count"» |
| P-C2 | When a bulk embedding request fails, the system retries in batches of up to 32 inputs before falling back to individual retries. (PR description) | 🟠 **not observed** | probe model-probe1, tc2_call_count: same on both sides: `6` | [probe-model-probe1-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc2_call_count"» |
| P-C3 | The system validates that the number of returned embeddings matches the number of inputs for bulk and batch requests, rejecting mismatched responses. (PR description) | ⚪ **not testable** | probe model-probe1 has no observation for this claim | no matching log line |
| P-C4 | Input order of embeddings is preserved in the output, matching the order of inputs. (PR description) | ⚪ **not testable** | probe model-probe1 has no observation for this claim | no matching log line |
| P-C5 | Partial-failure behavior (zero-vector placeholders for failed items) and total-failure behavior (raising exception when all items fail) are unchanged. (PR description) | ⚪ **not testable** | probe model-probe1 has no observation for this claim | no matching log line |

Citation check (WARN): 3 citation(s) verified; 3 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 43 / 47 | - |
| Tests unchanged | 43 | - |
| New tests that pass | 4 | - |
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

**model-probe1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe1.py`, frozen `a47f17cc6a6a` at 2026-10-21T19:50:32.190896+00:00): Testing the _embed_with_fallback function for batching behavior and error handling

- P-C1 (PR description): When a bulk embedding request succeeds, the system uses a single request (fast path unchanged). Expects the covered observations to stay the same.
- P-C2 (PR description): When a bulk embedding request fails, the system retries in batches of up to 32 inputs before falling back to individual retries. Expects the covered observations to differ.
- P-C3 (PR description): The system validates that the number of returned embeddings matches the number of inputs for bulk and batch requests, rejecting mismatched responses. Expects the covered observations to differ.
- P-C4 (PR description): Input order of embeddings is preserved in the output, matching the order of inputs. Expects the covered observations to stay the same.
- P-C5 (PR description): Partial-failure behavior (zero-vector placeholders for failed items) and total-failure behavior (raising exception when all items fail) are unchanged. Expects the covered observations to stay the same.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `tc1_call_count` | P-C1 | 🟢 **as claimed** | same on both sides: `1` | [probe-model-probe1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc1_call_count"»<br>[probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc1_call_count"» |
| `tc1_outcome` | P-C1 | 🟢 **as claimed** | same on both sides: `"OK:5"` | [probe-model-probe1-main-1.jsonl:2](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc1_outcome"»<br>[probe-model-probe1-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc1_outcome"» |
| `tc2_call_count` | P-C2 | 🟠 **no change although the claim says it changes** | same on both sides: `6` | [probe-model-probe1-main-1.jsonl:3](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc2_call_count"»<br>[probe-model-probe1-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc2_call_count"» |
| `tc2_outcome` | P-C2 | 🟠 **no change although the claim says it changes** | same on both sides: `"OK:5"` | [probe-model-probe1-main-1.jsonl:4](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc2_outcome"»<br>[probe-model-probe1-pr-1.jsonl:4](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc2_outcome"» |
| `tc3_call_count` | P-C2 | 🟢 **as claimed** | `value`: 1 -> 6 | [probe-model-probe1-main-1.jsonl:5](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc3_call_count"»<br>[probe-model-probe1-pr-1.jsonl:5](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc3_call_count"» |
| `tc3_outcome` | P-C2 | 🟢 **as claimed** | `value`: "OK:4" -> "OK:5" | [probe-model-probe1-main-1.jsonl:6](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc3_outcome"»<br>[probe-model-probe1-pr-1.jsonl:6](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc3_outcome"» |
| `tc4_call_count` | P-C2 | 🟠 **no change although the claim says it changes** | same on both sides: `6` | [probe-model-probe1-main-1.jsonl:7](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc4_call_count"»<br>[probe-model-probe1-pr-1.jsonl:7](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc4_call_count"» |
| `tc4_outcome` | P-C2 | 🟠 **no change although the claim says it changes** | same on both sides: `"EX:RuntimeError"` | [probe-model-probe1-main-1.jsonl:8](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc4_outcome"»<br>[probe-model-probe1-pr-1.jsonl:8](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc4_outcome"» |
| `tc5_call_count` | P-C2 | 🟢 **as claimed** | `value`: 1 -> 6 | [probe-model-probe1-main-1.jsonl:9](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc5_call_count"»<br>[probe-model-probe1-pr-1.jsonl:9](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc5_call_count"» |
| `tc5_outcome` | P-C2 | 🟢 **as claimed** | `value`: "OK:2" -> "OK:5" | [probe-model-probe1-main-1.jsonl:10](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl) «"observation": "tc5_outcome"»<br>[probe-model-probe1-pr-1.jsonl:10](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl) «"observation": "tc5_outcome"» |

Citation check (PASS): 20 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (4.4 s run).

Coverage gate (python, confidence normal): 24 of 24 changed executable line(s) ran (100%).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `pr_agent/tools/pr_similar_issue.py` | 24 | 24 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `c8a5bd91fcf5` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: all runs exited 0.
- Changed code was exercised (coverage gate): 24 of 24 changed executable line(s) ran (100%).
- Probes ran on both sides: 1 probe(s), 3 alternating runs per side, every run printed its observations.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 20 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Every claim cites a real log line | 🟠 **WARN** | 3 citation(s) verified; 3 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |
| Behavior difference found | 🟠 **finding** | probe: 4 observation(s) need attention: tc2_call_count does not differ although the claim says it does (C2); tc2_outcome does not differ although the claim says it does (C2); tc4_call_count does not differ although the claim says it does (C2); tc4_outcome does not differ although the claim says it does (C2); probe: claim(s) C1, C2 proven; tests: 43 test(s) ran on main, 47 on the PR; 4 new test(s) pass, 43 unchanged | This is about the PR, not the run: read the failing tests and their log lines and the Probes section, then decide. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | all runs exited 0 |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | 24 of 24 changed executable line(s) ran (100%) |
| Probes ran on both sides | 🟢 **PASS** | 1 probe(s), 3 alternating runs per side, every run printed its observations |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 3 citation(s) verified; 3 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 20 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/pr_agent-4189 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/The-PR-Agent/pr-agent/pull/4189
```

## Evidence links

- [Pull request The-PR-Agent/pr-agent#4189](https://github.com/The-PR-Agent/pr-agent/pull/4189)
- [record.json](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/coverage-pr.json)
- [probe-model-probe1-main-1.jsonl](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-main-1.jsonl)
- [probe-model-probe1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/probe-model-probe1-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:16](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pytest-main-1.log) «43 passed, 4 warnings in 2.02s»
- pr run 1 result: [pytest-pr-1.log:16](../../ops/runs/2026-10-22-check-0118/pr_agent-4189/pytest-pr-1.log) «47 passed, 4 warnings in 2.10s»

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
