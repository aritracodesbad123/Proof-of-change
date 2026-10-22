# Reviewer report: vllm-project/vllm#58715: [Metrics] Count finished requests by watermark status

Run `vllm-58715`, tested 2026-10-22 10:44 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 10:56 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** [Metrics] Count finished requests by watermark status ([vllm-project/vllm#58715](https://github.com/vllm-project/vllm/pull/58715)).
- **What we observed:** install failed (2); see setup-main.log.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 9.0 GB (of 15.6 GB).
- Setup check: free disk 89.0 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 8 results
- Query: vllm python setup install instructions https://github.com/vllm-project/vllm site:github.com/vllm-project/vllm
- Query: vllm python documentation install https://github.com/vllm-project/vllm site:github.com/vllm-project/vllm
- Query: vllm python install requirements https://pypi.org/project/vllm/ https://github.com/vllm-project/vllm site:pypi.org
- Source: vllm · PyPI — https://pypi.org/project/vllm/
- Source: vllm-ascend · PyPI — https://pypi.org/project/vllm-ascend/
- Source: vllm/docs/getting_started/installation/gpu.cuda.inc.md at main · vllm-project/vllm · GitHub — https://github.com/vllm-project/vllm/blob/main/docs/getting_started/installation/gpu.cuda.inc.md
- Source: [Installation]: pip install -e failed · Issue #5674 · vllm-project/vllm · GitHub — https://github.com/vllm-project/vllm/issues/5674
- Source: Releases · vllm-project/vllm · GitHub — https://github.com/vllm-project/vllm/releases
- Source: [Installation]: how to install v0.8.0 · Issue #15081 · vllm-project/vllm · GitHub — https://github.com/vllm-project/vllm/issues/15081
- Source: vllm/.gitignore at main · vllm-project/vllm · GitHub — https://github.com/vllm-project/vllm/blob/main/.gitignore
- Source: [Bug]: vllm ignores existing pytorch installation · Issue #21745 · vllm-project/vllm · GitHub — https://github.com/vllm-project/vllm/issues/21745
- Demo helper: source checkout succeeded after a setup retry.
- Setup plan: the same packages on main and pr.
- Setup plan: install pandas (listed in requirements.txt) on main and pr.
- Setup plan: install numpy>=1.24 (listed in requirements.txt) on main and pr.
- Setup plan: install aiohttp>=3.10 (listed in requirements.txt) on main and pr.
- Setup plan: install transformers>=4.46 (listed in requirements.txt) on main and pr.
- Setup plan: install xlsxwriter>=3.2.1 (listed in requirements.txt) on main and pr.
- Setup plan: install tqdm>=4.66 (listed in requirements.txt) on main and pr.
- Setup plan: install matplotlib (listed in requirements.txt) on main and pr.
- Setup plan: install seaborn (listed in requirements.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.11,<3.15, <3.15,>=3.11
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

- Tested `9370bbd91c74` of the PR against main (source-pair route).
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

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/vllm-58715 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/vllm-project/vllm/pull/58715
```

## Evidence links

- [Pull request vllm-project/vllm#58715](https://github.com/vllm-project/vllm/pull/58715)
- [record.json](../../ops/runs/2026-10-22-check-1044/vllm-58715/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-1044/vllm-58715/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-1044/vllm-58715/setup-main.log)
- [git.log](../../ops/runs/2026-10-22-check-1044/vllm-58715/git.log)

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
