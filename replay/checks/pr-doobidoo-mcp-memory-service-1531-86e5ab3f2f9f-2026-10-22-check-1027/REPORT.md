# Reviewer report: doobidoo/mcp-memory-service#1531: fix(maintenance): regenerate_embeddings writes vectors into their store partition

Run `mcp_memory_service-1531`, tested 2026-10-22 10:27 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 10:35 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** fix(maintenance): regenerate_embeddings writes vectors into their store partition ([doobidoo/mcp-memory-service#1531](https://github.com/doobidoo/mcp-memory-service/pull/1531)).
- **What we observed:** the run failed its own checks: pytest exit codes explained.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 8.3 GB (of 15.6 GB).
- Setup check: free disk 89.2 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: mcp-memory-service python setup install instructions https://github.com/doobidoo/mcp-memory-service site:github.com/doobidoo/mcp-memory-service
- Query: mcp-memory-service python documentation install https://github.com/doobidoo/mcp-memory-service site:github.com/doobidoo/mcp-memory-service
- Query: mcp-memory-service python install requirements https://pypi.org/project/mcp-memory-service/ https://github.com/doobidoo/mcp-memory-service site:pypi.org
- Source: mcp-memory-service · PyPI — https://pypi.org/project/mcp-memory-service/
- Source: GitHub - doobidoo/mcp-memory-service: Open-source persistent memory for AI agent pipelines (LangGraph, CrewAI, AutoGen) and Claude. REST API + knowledge graph + autonomous consolidation. · GitHub — https://github.com/doobidoo/mcp-memory-service
- Source: 01 Installation Guide · doobidoo/mcp-memory-service Wiki · GitHub — https://github.com/doobidoo/mcp-memory-service/wiki/01-Installation-Guide
- Source: [Feature]: Support for Python 3.14 by bumping supported tokenizers version to 0.22.2 · Issue #376 · doobidoo/mcp-memory-service · GitHub — https://github.com/doobidoo/mcp-memory-service/issues/376
- Source: mcp-memory-service/docs/ide-compatability.md at main · doobidoo/mcp-memory-service · GitHub — https://github.com/doobidoo/mcp-memory-service/blob/main/docs/ide-compatability.md
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
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🔴 **false** | 194 test(s) fail on the PR, e.g. tests.integration.test_cloudflare_connection::test_cloudflare_config | [pytest-pr-1.log:11811](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-pr-1.log) «ERROR tests/integration/test_cloudflare_connection.py::test_cloudflare_config» |
| P-C1 | regenerate_embeddings writes vectors into their store partition (PR description) | ⚪ **not testable** | probe model-probe1 has no observation for this claim | no matching log line |
| P-C2 | regenerate_embeddings now reads each memory's store and writes the vector into that partition (PR description) | ⚪ **not testable** | probe model-probe1 has no observation for this claim | no matching log line |
| P-C2 | regenerate_embeddings now reads each memory's store and writes the vector into that partition (PR description) | ⚪ **not testable** | probe model-probe2 has no observation for this claim | no matching log line |
| P-C3 | The import of serialize_float32 is corrected to come from the sqlite_vec package (PR description) | ⚪ **not testable** | probe model-probe3 has no observation for this claim | no matching log line |
| P-C4 | After the fix, a store-scoped retrieve finds the regenerated vector (PR description) | ⚪ **not testable** | probe model-probe4 has no observation for this claim | no matching log line |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 194 test(s) pass on main but fail on the PR, e.g. tests.integration.test_cloudflare_connection::test_cloudflare_config | [pytest-pr-1.log:11811](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-pr-1.log) «ERROR tests/integration/test_cloudflare_connection.py::test_cloudflare_config» |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 7 test(s) changed result in another way (for example passed -> skipped), e.g. tests.integration.test_cli_interfaces.TestCLIPerformance::test_memory_version_performance: failed -> error | [pytest-pr-1.log:12530](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-pr-1.log) «14 failed, 4144 passed, 126 skipped, 8 xfailed, 18274 warnings, 718 errors in 69.06s (0:01:09)» |

Citation check (WARN): 3 citation(s) verified; 5 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 4517 / 4517 | - |
| Tests unchanged | 4248 | - |
| New tests that pass | 2 | - |
| Tests that pass on main but fail on the PR | 194 | `tests.integration.test_cloudflare_connection::test_cloudflare_config`, `tests.integration.test_cloudflare_connection::test_storage_backend_import`, `tests.integration.test_concurrent_clients.TestConcurrentClients::test_multiple_readers_one_writer`, `tests.integration.test_concurrent_clients.TestConcurrentClients::test_reader_writer_concurrent`, `tests.integration.test_concurrent_clients.TestConcurrentClients::test_two_clients_concurrent_write` |
| Tests that are new in the PR and fail | 0 | - |
| Tests that ran on main but are missing on the PR side | 0 | - |
| Tests that changed result in another way (for example passed -> skipped) | 7 | `tests.integration.test_cli_interfaces.TestCLIPerformance::test_memory_version_performance: failed -> error`, `tests.storage.test_backend_store_signature_conformance::test_all_backends_implement_web_api_methods[get_conflicts]: error -> skipped`, `tests.storage.test_backend_store_signature_conformance::test_all_backends_implement_web_api_methods[get_graph_visualization_data]: error -> skipped`, `tests.storage.test_backend_store_signature_conformance::test_all_backends_implement_web_api_methods[get_relationship_type_distribution]: error -> skipped`, `tests.storage.test_backend_store_signature_conformance::test_all_backends_implement_web_api_methods[resolve_conflict]: error -> skipped` |
| Tests that gave different results between the 3 runs of the same side (flaky) | 0 | - |
| Tests that fail on main and pass on the PR | 200 | `tests.services.test_mistake_notes::test_mistake_note_delete`, `tests.services.test_mistake_notes::test_mistake_note_delete_nonexistent`, `tests.services.test_mistake_notes::test_mistake_note_delete_wrong_type`, `tests.services.test_mistake_notes::test_mistake_note_update_nonexistent`, `tests.services.test_mistake_notes::test_mistake_note_update_rejects_blanking_correct_action[   ]` |
| Tests that are new or changed but did not run because an optional module is missing | 0 | - |
| Tests that were re-parametrized (same test, new parameter ids; not counted as removed) | 0 | - |
| Test modules that fail to load on the PR side only (their tests no longer run) | 0 | - |
| Test modules that fail to load on main only (no baseline for their tests) | 0 | - |
| Test modules that fail to load on both sides (their tests did not run) | 0 | - |
| Tests that fail identically on both sides (already broken on main) | 176 | `tests.benchmarks.test_benchmark_devbench.TestIngestAndRetrieve::test_retrieve_exact_query_finds_something`, `tests.integration.test_cli_interfaces.TestCLIFunctionality::test_memory_status_command`, `tests.integration.test_cli_interfaces.TestCLIInterfaces::test_argument_compatibility`, `tests.integration.test_cli_interfaces.TestCLIInterfaces::test_memory_command_exists`, `tests.integration.test_cli_interfaces.TestCLIInterfaces::test_memory_server_command_exists` |

`tests.integration.test_cloudflare_connection::test_cloudflare_config` fails with: `failed on setup with "ValueError: I/O operation on closed file"`

`tests.integration.test_cloudflare_connection::test_storage_backend_import` fails with: `failed on setup with "ValueError: I/O operation on closed file"`

`tests.integration.test_concurrent_clients.TestConcurrentClients::test_multiple_readers_one_writer` fails with: `failed on setup with "ValueError: I/O operation on closed file"`

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-probe1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe1.py`, frozen `d899e2206799` at 2026-10-22T04:57:54.684729+00:00): Check that regenerate_embeddings writes vectors into store partition

- P-C1 (PR description): regenerate_embeddings writes vectors into their store partition Expects the covered observations to differ.
- P-C2 (PR description): regenerate_embeddings now reads each memory's store and writes the vector into that partition Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `error` | - | 🟢 **same on both sides** | same on both sides: `"ModuleNotFoundError"` | [probe-model-probe1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe1-main-1.jsonl) «"observation": "error"»<br>[probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe1-pr-1.jsonl) «"observation": "error"» |

**model-probe2** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe2.py`, frozen `6c1a8d11bbfc` at 2026-10-22T04:57:54.684870+00:00): Check that regenerate_embeddings reads each memory's store and writes vector into that partition

- P-C2 (PR description): regenerate_embeddings now reads each memory's store and writes the vector into that partition Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `error` | - | 🟢 **same on both sides** | same on both sides: `"ModuleNotFoundError"` | [probe-model-probe2-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe2-main-1.jsonl) «"observation": "error"»<br>[probe-model-probe2-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe2-pr-1.jsonl) «"observation": "error"» |

**model-probe3** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe3.py`, frozen `046eabb20dea` at 2026-10-22T04:57:54.684938+00:00): Check that import of serialize_float32 is corrected to come from sqlite_vec package

- P-C3 (PR description): The import of serialize_float32 is corrected to come from the sqlite_vec package Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `error` | - | 🟢 **same on both sides** | same on both sides: `"ModuleNotFoundError"` | [probe-model-probe3-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe3-main-1.jsonl) «"observation": "error"»<br>[probe-model-probe3-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe3-pr-1.jsonl) «"observation": "error"» |

**model-probe4** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe4.py`, frozen `733d191e3521` at 2026-10-22T04:57:54.685006+00:00): Check that after fix, a store-scoped retrieve finds the regenerated vector

- P-C4 (PR description): After the fix, a store-scoped retrieve finds the regenerated vector Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `error` | - | 🟢 **same on both sides** | same on both sides: `"ModuleNotFoundError"` | [probe-model-probe4-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe4-main-1.jsonl) «"observation": "error"»<br>[probe-model-probe4-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe4-pr-1.jsonl) «"observation": "error"» |

Citation check (PASS): 8 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: not needed** (no changed Python lines).

Coverage gate (no-executable-change, confidence normal): no executable code changed (docs, tests or config only), so there was nothing to cover.

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## Missing optional modules

- 2 unchanged test(s) skipped on both sides because `mcp_memory_service` is not installed (coverage gap, verdict unaffected).

## What went right

- Tested `86e5ab3f2f9f` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- Changed code was exercised (coverage gate): no executable code changed (docs, tests or config only), so there was nothing to cover.
- Probes ran on both sides: 4 probe(s), 3 alternating runs per side, every run printed its observations.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 8 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| pytest exit codes explained | 🔴 **FAIL** | pytest exit 1; 176 failure(s)/error(s) pre-existing and identical on both sides | Read the pytest logs: PR run 1: 2 failure(s) not seen on main; PR run 2: 2 failure(s) not seen on main |
| Optional modules installed | 🟠 **WARN** | unchanged tests skipped on both sides: mcp_memory_service (2) | Add the module(s) to optional_test_deps for this library in ops/daily_run.py and run again. |
| Every claim cites a real log line | 🟠 **WARN** | 3 citation(s) verified; 5 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🔴 **FAIL** | pytest exit 1; 176 failure(s)/error(s) pre-existing and identical on both sides |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | no executable code changed (docs, tests or config only), so there was nothing to cover |
| Optional modules installed | 🟠 **WARN** | unchanged tests skipped on both sides: mcp_memory_service (2) |
| Probes ran on both sides | 🟢 **PASS** | 4 probe(s), 3 alternating runs per side, every run printed its observations |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 3 citation(s) verified; 5 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 8 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/mcp_memory_service-1531 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/doobidoo/mcp-memory-service/pull/1531
```

## Evidence links

- [Pull request doobidoo/mcp-memory-service#1531](https://github.com/doobidoo/mcp-memory-service/pull/1531)
- [record.json](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/junit-pr-1.xml)
- [probe-model-probe1-main-1.jsonl](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe1-main-1.jsonl)
- [probe-model-probe1-pr-1.jsonl](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe1-pr-1.jsonl)
- [probe-model-probe2-main-1.jsonl](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe2-main-1.jsonl)
- [probe-model-probe2-pr-1.jsonl](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe2-pr-1.jsonl)
- [probe-model-probe3-main-1.jsonl](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe3-main-1.jsonl)
- [probe-model-probe3-pr-1.jsonl](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe3-pr-1.jsonl)
- [probe-model-probe4-main-1.jsonl](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe4-main-1.jsonl)
- [probe-model-probe4-pr-1.jsonl](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/probe-model-probe4-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:12885](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-main-1.log) «15 failed, 4134 passed, 122 skipped, 10 xfailed, 2 xpassed, 14195 warnings, 732 errors in 70.77s (0:01:10)»
- pr run 1 result: [pytest-pr-1.log:12530](../../ops/runs/2026-10-22-check-1027/mcp_memory_service-1531/pytest-pr-1.log) «14 failed, 4144 passed, 126 skipped, 8 xfailed, 18274 warnings, 718 errors in 69.06s (0:01:09)»

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
