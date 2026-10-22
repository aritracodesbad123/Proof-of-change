# Reviewer report: frappe/erpnext#61257: fix(accounts): validate payment mode accounts and enabled status

Run `erpnext-61257`, tested 2026-10-22 10:56 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 10:56 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** fix(accounts): validate payment mode accounts and enabled status ([frappe/erpnext#61257](https://github.com/frappe/erpnext/pull/61257)).
- **What we observed:** install failed (2); see setup-main.log.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 8.1 GB (of 15.6 GB).
- Setup check: free disk 88.2 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 9 results
- Query: erpnext python setup install instructions https://github.com/frappe/erpnext site:github.com/frappe/erpnext
- Query: erpnext python documentation install https://github.com/frappe/erpnext site:github.com/frappe/erpnext
- Query: erpnext python install requirements https://pypi.org/project/erpnext/ https://github.com/frappe/erpnext site:pypi.org
- Source: erpnext/README.md at develop · frappe/erpnext · GitHub — https://github.com/frappe/erpnext/blob/develop/README.md
- Source: frappe-bench · PyPI — https://pypi.org/project/frappe-bench/
- Source: caffeinated-whale-cli · PyPI — https://pypi.org/project/caffeinated-whale-cli/
- Source: ws-frappe-cli · PyPI — https://pypi.org/project/ws-frappe-cli/
- Source: GitHub - frappe/erpnext: Free and Open Source Enterprise Resource Planning (ERP) · GitHub — https://github.com/frappe/erpnext
- Source: Easy install setup guide for Ubuntu 20.04 LTS  · Issue #22125 · frappe/erpnext · GitHub — https://github.com/frappe/erpnext/issues/22125
- Source: GitHub - frappe/erpnext-14: Free and Open Source Enterprise Resource Planning (ERP) · GitHub — https://github.com/frappe/erpnext-14
- Source: GitHub - frappe/erpnext: Free and Open Source Enterprise ... — https://github.com/frappe/erpnext/tree/develop
- Source: Releases · frappe/erpnext · GitHub — https://github.com/frappe/erpnext/releases
- Setup plan: the same packages on main and pr.
- Setup plan: Unidecode is noted, installed with the project.
- Setup plan: barcodenumber is noted, installed with the project.
- Setup plan: rapidfuzz is noted, installed with the project.
- Setup plan: holidays is noted, installed with the project.
- Setup plan: googlemaps is noted, installed with the project.
- Setup plan: plaid-python is noted, installed with the project.
- Setup plan: python-youtube is noted, installed with the project.
- Setup plan: pypng is noted, installed with the project.
- Setup plan: mt-940 is noted, installed with the project.
- Setup plan: pdfplumber is noted, installed with the project.
- Setup plan: Python 3.14: switched the local sandbox to <home>
- rerun, setup problem: main install failed after 3 tries.
- Demo helper: setup failure already labelled; the probe was not rerun.

## Claims vs reality

No tests ran, so no claim could be checked.

## What changed in behavior

Not measured: install failed (2); see setup-main.log.

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

No probes ran: this record predates probes.

## Was the changed code exercised?

**Coverage: NOT MEASURED, record predates the coverage gate.** No coverage run exists for this record; nothing below is a measurement.

Coverage gate (python, confidence lower): coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result).

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `7feeb6fae172` of the PR against main (source-pair route).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | install failed (2); see setup-main.log | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) | Not a measurement: this record is older than the coverage gate. Re-run the PR with the current ops/daily_run.py to measure it. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| Changed code was exercised (coverage gate) | 🟠 **WARN** | coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result) |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | ⚪ **SKIP** | no log lines to cite (no tests ran) |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/erpnext-61257 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/frappe/erpnext/pull/61257
```

## Evidence links

- [Pull request frappe/erpnext#61257](https://github.com/frappe/erpnext/pull/61257)
- [record.json](../../ops/runs/2026-10-22-check-1056/erpnext-61257/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-1056/erpnext-61257/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-1056/erpnext-61257/setup-main.log)
- [git.log](../../ops/runs/2026-10-22-check-1056/erpnext-61257/git.log)

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
