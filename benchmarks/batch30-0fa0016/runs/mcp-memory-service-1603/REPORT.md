# Reviewer report: doobidoo/mcp-memory-service#1603: fix(mcp): propagate tool exceptions so failures reach the client as isError (#1601)

Run `mcp_memory_service-1603`, tested 2026-10-22 10:58 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 11:03 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## 🟠 NEEDS ATTENTION
>
> **Recommended action:** Reject  
> **Confidence:** Medium. The run is trustworthy and found a difference a person should look at. Some checks gave warnings: Changed code was exercised (coverage gate); Every claim cites a real log line
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** fix(mcp): propagate tool exceptions so failures reach the client as isError (#1601) ([doobidoo/mcp-memory-service#1603](https://github.com/doobidoo/mcp-memory-service/pull/1603)).
- **What we observed:** probe: 4 observation(s) need attention: refused.exception_raised differs and no claim covers it; refused.first_element_text differs and no claim covers it; refused.first_element_type differs and no claim covers it; refused.return_type differs and no claim covers it; rejected: claim pattern(s) C1, C2, C3 match none of this probe's observation names, so the probe is not counted; tests: 29 test(s) ran on main, 35 on the PR; 6 new test(s) pass, 30 unchanged (1 of them skipped on both sides).
- **What you should do:** Do not approve as is. Read 'What changed in behavior' and decide with the PR author.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 8.0 GB (of 15.6 GB).
- Setup check: free disk 87.9 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: mcp-memory-service python setup install instructions https://github.com/doobidoo/mcp-memory-service site:github.com/doobidoo/mcp-memory-service
- Query: mcp-memory-service python documentation install https://github.com/doobidoo/mcp-memory-service site:github.com/doobidoo/mcp-memory-service
- Query: mcp-memory-service python install requirements https://pypi.org/project/mcp-memory-service/ https://github.com/doobidoo/mcp-memory-service site:pypi.org
- Source: mcp-memory-service · PyPI — https://pypi.org/project/mcp-memory-service/
- Source: mcp-memory-service/docs/setup-guide.md at main · doobidoo/mcp-memory-service · GitHub — https://github.com/doobidoo/mcp-memory-service/blob/main/docs/setup-guide.md
- Source: GitHub - doobidoo/mcp-memory-service: Open-source persistent memory for AI agent pipelines (LangGraph, CrewAI, AutoGen) and Claude. REST API + knowledge graph + autonomous consolidation. · GitHub — https://github.com/doobidoo/mcp-memory-service
- Source: 01 Installation Guide · doobidoo/mcp-memory-service Wiki · GitHub — https://github.com/doobidoo/mcp-memory-service/wiki/01-Installation-Guide
- Source: Presume I know nothing about the underlying technology and please explain how to start using this project · doobidoo/mcp-memory-service · Discussion #525 · GitHub — https://github.com/doobidoo/mcp-memory-service/discussions/525
- Setup plan: the same packages on main and pr.
- Setup plan: aiofiles is noted, installed with the project.
- Setup plan: aiohttp is noted, installed with the project.
- Setup plan: aiosqlite is noted, installed with the project.
- Setup plan: apscheduler is noted, installed with the project.
- Setup plan: authlib is noted, installed with the project.
- Setup plan: build is noted, installed with the project.
- Setup plan: chardet is noted, installed with the project.
- Setup plan: click is noted, installed with the project.
- Setup plan: cryptography is noted, installed with the project.
- Setup plan: fastapi is noted, installed with the project.
- Setup plan: httpx is noted, installed with the project.
- Setup plan: mcp is noted, installed with the project.
- Setup plan: numpy is noted, installed with the project.
- Setup plan: psutil is noted, installed with the project.
- Setup plan: PyJWT is noted, installed with the project.
- Setup plan: pypdf is noted, installed with the project.
- Setup plan: PyYAML is noted, installed with the project.
- Setup plan: python-dotenv is noted, installed with the project.
- Setup plan: python-multipart is noted, installed with the project.
- Setup plan: requests is noted, installed with the project.
- Setup plan: sqlite-vec is noted, installed with the project.
- Setup plan: sse-starlette is noted, installed with the project.
- Setup plan: typing-extensions is noted, installed with the project.
- Setup plan: uvicorn is noted, installed with the project.
- Setup plan: zeroconf is noted, installed with the project.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.10

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (30 unchanged, 3 runs per side) | [pytest-pr-1.log:64](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pytest-pr-1.log) «35 passed, 1 skipped, 172 warnings in 8.41s» |
| P-C1 | A tool call that fails now answers with `isError: true`. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C2 | Before, the envelope said `isError: false` and carried the error text as ordinary content (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C3 | New integration test on the real streamable-http transport: a refused write yields `isError: true`, an accepted write yields `false`. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| - | Change not in the PR description (probe model-p1) | 🟠 **unmentioned change** | refused.exception_raised: `value`: null -> "RuntimeError" | [probe-model-p1-pr-1.jsonl:5](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "refused.exception_raised"» |
| - | Change not in the PR description (probe model-p1) | 🟠 **unmentioned change** | refused.first_element_text: `value`: "Error storing memory: Duplicate cont... -> null | [probe-model-p1-pr-1.jsonl:6](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "refused.first_element_text"» |
| - | Change not in the PR description (probe model-p1) | 🟠 **unmentioned change** | refused.first_element_type: `value`: "types.TextContent" -> null | [probe-model-p1-pr-1.jsonl:7](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "refused.first_element_type"» |
| - | Change not in the PR description (probe model-p1) | 🟠 **unmentioned change** | refused.return_type: `value`: "list" -> null | [probe-model-p1-pr-1.jsonl:8](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "refused.return_type"» |

Citation check (WARN): 5 citation(s) verified; 3 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 29 / 35 | - |
| Tests unchanged | 30 | - |
| New tests that pass | 6 | - |
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

**model-p1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-p1.py`, frozen `ea8cd8e61b5d` at 2026-10-22T05:31:27.779695+00:00): handler.handle_store_memory

- P-C1 (PR description): A tool call that fails now answers with `isError: true`. Expects the covered observations to differ.
- P-C2 (PR description): Before, the envelope said `isError: false` and carried the error text as ordinary content Expects the covered observations to stay the same.
- P-C3 (PR description): New integration test on the real streamable-http transport: a refused write yields `isError: true`, an accepted write yields `false`. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `accepted.exception_raised` | - | 🟢 **same on both sides** | same on both sides: `null` | [probe-model-p1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-main-1.jsonl) «"observation": "accepted.exception_raised"»<br>[probe-model-p1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "accepted.exception_raised"» |
| `accepted.first_element_text` | - | 🟢 **same on both sides** | same on both sides: `"Memory stored successfully (hash: abc123)"` | [probe-model-p1-main-1.jsonl:2](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-main-1.jsonl) «"observation": "accepted.first_element_text"»<br>[probe-model-p1-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "accepted.first_element_text"» |
| `accepted.first_element_type` | - | 🟢 **same on both sides** | same on both sides: `"types.TextContent"` | [probe-model-p1-main-1.jsonl:3](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-main-1.jsonl) «"observation": "accepted.first_element_type"»<br>[probe-model-p1-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "accepted.first_element_type"» |
| `accepted.return_type` | - | 🟢 **same on both sides** | same on both sides: `"list"` | [probe-model-p1-main-1.jsonl:4](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-main-1.jsonl) «"observation": "accepted.return_type"»<br>[probe-model-p1-pr-1.jsonl:4](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "accepted.return_type"» |
| `refused.exception_raised` | - | 🟠 **differs, not in the PR description** | `value`: null -> "RuntimeError" | [probe-model-p1-main-1.jsonl:5](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-main-1.jsonl) «"observation": "refused.exception_raised"»<br>[probe-model-p1-pr-1.jsonl:5](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "refused.exception_raised"» |
| `refused.first_element_text` | - | 🟠 **differs, not in the PR description** | `value`: "Error storing memory: Duplicate cont... -> null | [probe-model-p1-main-1.jsonl:6](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-main-1.jsonl) «"observation": "refused.first_element_text"»<br>[probe-model-p1-pr-1.jsonl:6](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "refused.first_element_text"» |
| `refused.first_element_type` | - | 🟠 **differs, not in the PR description** | `value`: "types.TextContent" -> null | [probe-model-p1-main-1.jsonl:7](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-main-1.jsonl) «"observation": "refused.first_element_type"»<br>[probe-model-p1-pr-1.jsonl:7](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "refused.first_element_type"» |
| `refused.return_type` | - | 🟠 **differs, not in the PR description** | `value`: "list" -> null | [probe-model-p1-main-1.jsonl:8](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-main-1.jsonl) «"observation": "refused.return_type"»<br>[probe-model-p1-pr-1.jsonl:8](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl) «"observation": "refused.return_type"» |

**diff-api** (diff (auto-derived from base-side code, model-free); informational under baseline full, `diff-probes/diff-api.py`, frozen `bbd984c32288` at 2026-10-22T05:31:27.814767+00:00): Public functions touched by the PR, called with type-appropriate inputs on both sides.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input0` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input0"»<br>[probe-diff-api-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input0"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input1` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:2](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input1"»<br>[probe-diff-api-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input1"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input10` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:3](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input10"»<br>[probe-diff-api-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input10"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input11` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:4](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input11"»<br>[probe-diff-api-pr-1.jsonl:4](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input11"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input12` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:5](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input12"»<br>[probe-diff-api-pr-1.jsonl:5](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input12"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input2` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:6](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input2"»<br>[probe-diff-api-pr-1.jsonl:6](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input2"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input3` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:7](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input3"»<br>[probe-diff-api-pr-1.jsonl:7](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input3"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input4` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:8](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input4"»<br>[probe-diff-api-pr-1.jsonl:8](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input4"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input5` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:9](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input5"»<br>[probe-diff-api-pr-1.jsonl:9](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input5"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input6` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:10](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input6"»<br>[probe-diff-api-pr-1.jsonl:10](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input6"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input7` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:11](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input7"»<br>[probe-diff-api-pr-1.jsonl:11](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input7"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input8` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:12](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input8"»<br>[probe-diff-api-pr-1.jsonl:12](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input8"» |
| `mcp_memory_service.server.handlers.memory.handle_memory_observe.input9` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_memory_observe>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:13](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input9"»<br>[probe-diff-api-pr-1.jsonl:13](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_memory_observe.input9"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input0` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:14](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input0"»<br>[probe-diff-api-pr-1.jsonl:14](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input0"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input1` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:15](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input1"»<br>[probe-diff-api-pr-1.jsonl:15](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input1"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input10` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:16](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input10"»<br>[probe-diff-api-pr-1.jsonl:16](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input10"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input11` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:17](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input11"»<br>[probe-diff-api-pr-1.jsonl:17](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input11"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input12` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:18](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input12"»<br>[probe-diff-api-pr-1.jsonl:18](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input12"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input2` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:19](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input2"»<br>[probe-diff-api-pr-1.jsonl:19](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input2"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input3` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:20](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input3"»<br>[probe-diff-api-pr-1.jsonl:20](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input3"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input4` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:21](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input4"»<br>[probe-diff-api-pr-1.jsonl:21](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input4"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input5` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:22](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input5"»<br>[probe-diff-api-pr-1.jsonl:22](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input5"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input6` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:23](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input6"»<br>[probe-diff-api-pr-1.jsonl:23](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input6"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input7` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:24](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input7"»<br>[probe-diff-api-pr-1.jsonl:24](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input7"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input8` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:25](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input8"»<br>[probe-diff-api-pr-1.jsonl:25](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input8"» |
| `mcp_memory_service.server.handlers.memory.handle_store_memory.input9` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_memory>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:26](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input9"»<br>[probe-diff-api-pr-1.jsonl:26](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_memory.input9"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input0` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:27](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input0"»<br>[probe-diff-api-pr-1.jsonl:27](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input0"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input1` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:28](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input1"»<br>[probe-diff-api-pr-1.jsonl:28](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input1"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input10` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:29](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input10"»<br>[probe-diff-api-pr-1.jsonl:29](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input10"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input11` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:30](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input11"»<br>[probe-diff-api-pr-1.jsonl:30](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input11"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input12` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:31](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input12"»<br>[probe-diff-api-pr-1.jsonl:31](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input12"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input2` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:32](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input2"»<br>[probe-diff-api-pr-1.jsonl:32](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input2"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input3` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:33](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input3"»<br>[probe-diff-api-pr-1.jsonl:33](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input3"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input4` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:34](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input4"»<br>[probe-diff-api-pr-1.jsonl:34](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input4"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input5` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:35](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input5"»<br>[probe-diff-api-pr-1.jsonl:35](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input5"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input6` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:36](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input6"»<br>[probe-diff-api-pr-1.jsonl:36](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input6"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input7` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:37](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input7"»<br>[probe-diff-api-pr-1.jsonl:37](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input7"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input8` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:38](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input8"»<br>[probe-diff-api-pr-1.jsonl:38](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input8"» |
| `mcp_memory_service.server.handlers.memory.handle_store_session.input9` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object handle_store_session>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:39](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input9"»<br>[probe-diff-api-pr-1.jsonl:39](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.server.handlers.memory.handle_store_session.input9"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input0` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:40](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input0"»<br>[probe-diff-api-pr-1.jsonl:40](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input0"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input1` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:41](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input1"»<br>[probe-diff-api-pr-1.jsonl:41](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input1"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input10` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:42](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input10"»<br>[probe-diff-api-pr-1.jsonl:42](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input10"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input11` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:43](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input11"»<br>[probe-diff-api-pr-1.jsonl:43](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input11"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input12` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:44](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input12"»<br>[probe-diff-api-pr-1.jsonl:44](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input12"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input2` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:45](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input2"»<br>[probe-diff-api-pr-1.jsonl:45](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input2"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input3` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:46](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input3"»<br>[probe-diff-api-pr-1.jsonl:46](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input3"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input4` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:47](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input4"»<br>[probe-diff-api-pr-1.jsonl:47](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input4"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input5` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:48](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input5"»<br>[probe-diff-api-pr-1.jsonl:48](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input5"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input6` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:49](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input6"»<br>[probe-diff-api-pr-1.jsonl:49](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input6"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input7` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:50](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input7"»<br>[probe-diff-api-pr-1.jsonl:50](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input7"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input8` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:51](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input8"»<br>[probe-diff-api-pr-1.jsonl:51](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input8"» |
| `mcp_memory_service.web.api.mcp.mcp_endpoint.input9` | - | 🟢 **same on both sides** | same on both sides: `{"repr": "<coroutine object mcp_endpoint>", "type": "coroutine"}` | [probe-diff-api-main-1.jsonl:52](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input9"»<br>[probe-diff-api-pr-1.jsonl:52](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl) «"observation": "mcp_memory_service.web.api.mcp.mcp_endpoint.input9"» |

Citation check (PASS): 120 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: NOT MEASURED** (the coverage report leaves out changed file(s): src/mcp_memory_service/web/api/mcp.py).

Coverage gate (python, confidence lower): coverage of the changed Python lines was NOT MEASURED (the coverage report leaves out changed file(s): src/mcp_memory_service/web/api/mcp.py).

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `f8760d36e773` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: all runs exited 0.
- Probes ran on both sides: 2 probe(s), 3 alternating runs per side, every run printed its observations.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 120 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (the coverage report leaves out changed file(s): src/mcp_memory_service/web/api/mcp.py) | The coverage run did not produce data (see coverage.why); run the check again. |
| Every claim cites a real log line | 🟠 **WARN** | 5 citation(s) verified; 3 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |
| Behavior difference found | 🟠 **finding** | probe: 4 observation(s) need attention: refused.exception_raised differs and no claim covers it; refused.first_element_text differs and no claim covers it; refused.first_element_type differs and no claim covers it; refused.return_type differs and no claim covers it; rejected: claim pattern(s) C1, C2, C3 match none of this probe's observation names, so the probe is not counted; tests: 29 test(s) ran on main, 35 on the PR; 6 new test(s) pass, 30 unchanged (1 of them skipped on both sides) | This is about the PR, not the run: read the failing tests and their log lines, then decide. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | all runs exited 0 |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (the coverage report leaves out changed file(s): src/mcp_memory_service/web/api/mcp.py) |
| Probes ran on both sides | 🟢 **PASS** | 2 probe(s), 3 alternating runs per side, every run printed its observations |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 5 citation(s) verified; 3 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 120 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/mcp_memory_service-1603 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/doobidoo/mcp-memory-service/pull/1603
```

## Evidence links

- [Pull request doobidoo/mcp-memory-service#1603](https://github.com/doobidoo/mcp-memory-service/pull/1603)
- [record.json](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/coverage-pr.json)
- [probe-model-p1-main-1.jsonl](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-main-1.jsonl)
- [probe-model-p1-pr-1.jsonl](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-model-p1-pr-1.jsonl)
- [probe-diff-api-main-1.jsonl](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-main-1.jsonl)
- [probe-diff-api-pr-1.jsonl](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/probe-diff-api-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:52](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pytest-main-1.log) «29 passed, 1 skipped, 153 warnings in 3.69s»
- pr run 1 result: [pytest-pr-1.log:64](../../ops/runs/2026-10-22-check-1058/mcp_memory_service-1603/pytest-pr-1.log) «35 passed, 1 skipped, 172 warnings in 8.41s»

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
