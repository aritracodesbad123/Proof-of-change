# Reviewer report: basetenlabs/truss#2682: fix: return 503 for model not ready on draft/watch deployments

Run `truss-2682`, tested 2026-10-22 10:39 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 10:41 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** fix: return 503 for model not ready on draft/watch deployments ([basetenlabs/truss#2682](https://github.com/basetenlabs/truss/pull/2682)).
- **What we observed:** tests produced no results on one side (collection failed; see pytest logs); probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 8.3 GB (of 15.6 GB).
- Setup check: free disk 89.3 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 6 results
- Query: truss python setup install instructions https://github.com/basetenlabs/truss site:github.com/basetenlabs/truss
- Query: truss python documentation install https://github.com/basetenlabs/truss site:github.com/basetenlabs/truss
- Query: truss python install requirements https://pypi.org/project/truss/ https://github.com/basetenlabs/truss site:pypi.org
- Source: truss-examples/comfyui-truss/README.md at main · basetenlabs/truss-examples · GitHub — https://github.com/basetenlabs/truss-examples/blob/main/comfyui-truss/README.md
- Source: truss-transfer · PyPI — https://pypi.org/project/truss-transfer/
- Source: truss · PyPI — https://pypi.org/project/truss/
- Source: pip install --upgrade truss not working · Issue #856 — https://github.com/basetenlabs/truss/issues/856
- Source: GitHub - basetenlabs/truss: The simplest way to serve AI/ML models in production · GitHub — https://github.com/basetenlabs/truss
- Source: GitHub - basetenlabs/truss-examples: Examples of models deployable with Truss · GitHub — https://github.com/basetenlabs/truss-examples
- Setup plan: the same packages on main and pr.
- Setup plan: huggingface_hub is noted, installed with the project.
- Setup plan: pydantic is noted, installed with the project.
- Setup plan: PyYAML is noted, installed with the project.
- Setup plan: tomlkit is noted, installed with the project.
- Setup plan: Jinja2 is noted, installed with the project.
- Setup plan: aiofiles is noted, installed with the project.
- Setup plan: blake3 is noted, installed with the project.
- Setup plan: boto3 is noted, installed with the project.
- Setup plan: click is noted, installed with the project.
- Setup plan: google-cloud-storage is noted, installed with the project.
- Setup plan: httpx is noted, installed with the project.
- Setup plan: httpx-ws is noted, installed with the project.
- Setup plan: inquirerpy is noted, installed with the project.
- Setup plan: keyring is noted, installed with the project.
- Setup plan: libcst is noted, installed with the project.
- Setup plan: loguru is noted, installed with the project.
- Setup plan: packaging is noted, installed with the project.
- Setup plan: pathspec is noted, installed with the project.
- Setup plan: psutil is noted, installed with the project.
- Setup plan: python-json-logger is noted, installed with the project.
- Setup plan: python-on-whales is noted, installed with the project.
- Setup plan: requests is noted, installed with the project.
- Setup plan: rich is noted, installed with the project.
- Setup plan: rich-click is noted, installed with the project.
- Setup plan: ruff is noted, installed with the project.
- Setup plan: tenacity is noted, installed with the project.
- Setup plan: watchfiles is noted, installed with the project.
- Setup plan: truss-transfer is noted, installed with the project.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.9,<3.15, <3.15,>=3.9

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| P-C1 | When a ModelNotReady exception is raised, the API returns a 503 Service Unavailable response with a JSON body instead of a 500 Internal Server Error. (PR description) | ⚪ **not testable** | probe model-p1, probe.error: same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-p1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1039/truss-2682/probe-model-p1-pr-1.jsonl) «"observation": "probe.error"» |

Citation check (PASS): 1 citation(s), every one re-read from its log file and matched.

## What changed in behavior

Not measured: tests produced no results on one side (collection failed; see pytest logs); probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count.

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-p1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-p1.py`, frozen `293dd760f055` at 2026-10-22T05:10:59.878261+00:00): Test the behavior of SanitizedExceptionMiddleware when encountering ModelNotReady vs. other exceptions.

- P-C1 (PR description): When a ModelNotReady exception is raised, the API returns a 503 Service Unavailable response with a JSON body instead of a 500 Internal Server Error. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | P-C1 | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-p1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1039/truss-2682/probe-model-p1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-p1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1039/truss-2682/probe-model-p1-pr-1.jsonl) «"observation": "probe.error"» |

Citation check (PASS): 2 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: NOT MEASURED, record predates the coverage gate.** No coverage run exists for this record; nothing below is a measurement.

Coverage gate (python, confidence lower): coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result).

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `cecc3606d9c7` of the PR against main (source-pair route).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every claim cites a real log line: 1 citation(s), every one re-read from its log file and matched.
- Every probe observation cites its output line: 2 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | tests produced no results on one side (collection failed; see pytest logs); probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| 3 alternating runs per side | 🔴 **FAIL** | main 3, PR 3 of 0 | Re-run with the default --runs 3 and look for timeouts in the pytest logs. |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) | Not a measurement: this record is older than the coverage gate. Re-run the PR with the current ops/daily_run.py to measure it. |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🔴 **FAIL** | main 3, PR 3 of 0 |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟢 **PASS** | 1 citation(s), every one re-read from its log file and matched |
| Every probe observation cites its output line | 🟢 **PASS** | 2 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/truss-2682 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/basetenlabs/truss/pull/2682
```

## Evidence links

- [Pull request basetenlabs/truss#2682](https://github.com/basetenlabs/truss/pull/2682)
- [record.json](../../ops/runs/2026-10-22-check-1039/truss-2682/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-1039/truss-2682/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-1039/truss-2682/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-1039/truss-2682/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-1039/truss-2682/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-1039/truss-2682/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-1039/truss-2682/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-1039/truss-2682/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-1039/truss-2682/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-1039/truss-2682/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-1039/truss-2682/pytest-pr-3.log)
- [probe-model-p1-main-1.jsonl](../../ops/runs/2026-10-22-check-1039/truss-2682/probe-model-p1-main-1.jsonl)
- [probe-model-p1-pr-1.jsonl](../../ops/runs/2026-10-22-check-1039/truss-2682/probe-model-p1-pr-1.jsonl)

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
