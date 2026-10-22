# Reviewer report: oyvindwe/connectlife-ha#742: Start WM26 G400 with program options, also from standby

Run `connectlife_ha-742`, tested 2026-10-22 10:57 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 10:58 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Start WM26 G400 with program options, also from standby ([oyvindwe/connectlife-ha#742](https://github.com/oyvindwe/connectlife-ha/pull/742)).
- **What we observed:** the run failed its own checks: 3 alternating runs per side.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 8.1 GB (of 15.6 GB).
- Setup check: free disk 88.1 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: connectlife-ha python setup install instructions https://github.com/oyvindwe/connectlife-ha site:github.com/oyvindwe/connectlife-ha
- Query: connectlife-ha python documentation install https://github.com/oyvindwe/connectlife-ha site:github.com/oyvindwe/connectlife-ha
- Query: connectlife-ha python install requirements https://pypi.org/project/connectlife-ha/ https://github.com/oyvindwe/connectlife-ha site:pypi.org
- Source: README.md - oyvindwe/connectlife-ha — https://github.com/oyvindwe/connectlife-ha/blob/main/custom_components/connectlife/data_dictionaries/README.md
- Source: Add data dictionary for Dehumidifier 007-499 (Hisense ... — https://github.com/oyvindwe/connectlife-ha/issues/546
- Source: AC light behavior · Issue #340 · oyvindwe/connectlife-ha · GitHub — https://github.com/oyvindwe/connectlife-ha/issues/340
- Source: GitHub - oyvindwe/connectlife-ha: ConnectLife integration for Home Assistant · GitHub — https://github.com/oyvindwe/connectlife-ha
- Source: ConnectLife integration stopped working · Issue #352 · oyvindwe/connectlife-ha · GitHub — https://github.com/oyvindwe/connectlife-ha/issues/352
- Setup plan: the same packages on main and pr.
- Setup plan: connectlife is noted, installed with the project.
- Setup plan: Python 3.13: switched the local sandbox to /usr/bin/python3.13
- Setup plan: refused python: no network or the package was not found
- Setup plan: refused connectlife.dump: no network or the package was not found

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| P-C2 | Start is available in standby as well as program select, and starting from standby with the full command works. (PR description) | 🟠 **not observed** | probe model-probe1, C2.import_error: same on both sides: `"ModuleNotFoundError"` | [probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe1-pr-1.jsonl) «"observation": "C2.import_error"» |
| P-C3 | `available_when` now accepts a list of allowed values per property. (PR description) | 🟠 **not observed** | probe model-probe2, C3.import_error: same on both sides: `"ModuleNotFoundError"` | [probe-model-probe2-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe2-pr-1.jsonl) «"observation": "C3.import_error"» |

Citation check (PASS): 2 citation(s), every one re-read from its log file and matched.

## What changed in behavior

Not measured: probe: 2 observation(s) need attention: C2.import_error does not differ although the claim says it does (C2); C3.import_error does not differ although the claim says it does (C3); probe model-probe1 has no measured line coverage (coverage produced no data (exit 0); see probe-coverage.log); it does not count as covering the change; probe model-probe2 has no measured line coverage (coverage produced no data (exit 0); see probe-coverage.log); it does not count as covering the change; tests: tests produced no results on one side (collection failed; see pytest logs).

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-probe1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe1.py`, frozen `2afa1f2e49b7` at 2026-10-22T05:28:00.714376+00:00): Tests the availability mechanism for buttons (claim C2)

- P-C2 (PR description): Start is available in standby as well as program select, and starting from standby with the full command works. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `C2.import_error` | P-C2 | 🟠 **no change although the claim says it changes** | same on both sides: `"ModuleNotFoundError"` | [probe-model-probe1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe1-main-1.jsonl) «"observation": "C2.import_error"»<br>[probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe1-pr-1.jsonl) «"observation": "C2.import_error"» |

**model-probe2** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe2.py`, frozen `c88bec690bd3` at 2026-10-22T05:28:00.714539+00:00): Tests the available_when structure change (claim C3)

- P-C3 (PR description): `available_when` now accepts a list of allowed values per property. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `C3.import_error` | P-C3 | 🟠 **no change although the claim says it changes** | same on both sides: `"ModuleNotFoundError"` | [probe-model-probe2-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe2-main-1.jsonl) «"observation": "C3.import_error"»<br>[probe-model-probe2-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe2-pr-1.jsonl) «"observation": "C3.import_error"» |

Citation check (PASS): 4 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: NOT MEASURED, record predates the coverage gate.** No coverage run exists for this record; nothing below is a measurement.

Coverage gate (python, confidence lower): coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result).

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `52bc2901d18f` of the PR against main (source-pair route).
- Probes ran on both sides: 2 probe(s), 3 alternating runs per side, every run printed its observations.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every claim cites a real log line: 2 citation(s), every one re-read from its log file and matched.
- Every probe observation cites its output line: 4 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| 3 alternating runs per side | 🔴 **FAIL** | main 3, PR 3 of 0 | Re-run with the default --runs 3 and look for timeouts in the pytest logs. |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) | Not a measurement: this record is older than the coverage gate. Re-run the PR with the current ops/daily_run.py to measure it. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🔴 **FAIL** | main 3, PR 3 of 0 |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) |
| Probes ran on both sides | 🟢 **PASS** | 2 probe(s), 3 alternating runs per side, every run printed its observations |
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

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/connectlife_ha-742 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/oyvindwe/connectlife-ha/pull/742
```

## Evidence links

- [Pull request oyvindwe/connectlife-ha#742](https://github.com/oyvindwe/connectlife-ha/pull/742)
- [record.json](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/pytest-pr-3.log)
- [probe-model-probe1-main-1.jsonl](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe1-main-1.jsonl)
- [probe-model-probe1-pr-1.jsonl](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe1-pr-1.jsonl)
- [probe-model-probe2-main-1.jsonl](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe2-main-1.jsonl)
- [probe-model-probe2-pr-1.jsonl](../../ops/runs/2026-10-22-check-1057/connectlife_ha-742/probe-model-probe2-pr-1.jsonl)

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
