# Reviewer report: macs3-project/MACS#784: Reject truncated BAM alignment records

Run `macs-784`, tested 2026-10-22 02:01 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 07:43 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Reject truncated BAM alignment records ([macs3-project/MACS#784](https://github.com/macs3-project/MACS/pull/784)).
- **What we observed:** install failed (1); see setup-main.log.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.2 GB (of 15.6 GB).
- Setup check: free disk 92.4 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 7 results
- Query: MACS python setup install instructions https://github.com/macs3-project/MACS site:github.com/macs3-project/MACS
- Query: MACS python documentation install https://github.com/macs3-project/MACS site:github.com/macs3-project/MACS
- Query: MACS python install requirements https://pypi.org/project/MACS/ https://github.com/macs3-project/MACS site:pypi.org
- Source: MACS · PyPI — https://pypi.org/project/MACS/
- Source: MACS2 · PyPI — https://pypi.org/project/macs2/
- Source: MACS3 · PyPI — https://pypi.org/project/macs3/
- Source: ERROR: Could not build wheels for MACS2, which is required to install pyproject.toml-based projects · macs3-project/MACS · Discussion #568 · GitHub — https://github.com/macs3-project/MACS/discussions/568
- Source: Install macs2 · macs3-project/MACS Wiki — https://github.com/macs3-project/MACS/wiki/Install-macs2
- Source: GitHub - macs3-project/MACS: MACS -- Model-based Analysis of ChIP-Seq · GitHub — https://github.com/macs3-project/MACS
- Source: Releases · macs3-project/MACS - GitHub — https://github.com/macs3-project/MACS/releases?after=v2.2.7
- Setup plan: the same packages on main and pr.
- Setup plan: numpy is noted, installed with the project.
- Setup plan: scipy is noted, installed with the project.
- Setup plan: pandas is noted, installed with the project.
- Setup plan: anndata is noted, installed with the project.
- Setup plan: hmmlearn is noted, installed with the project.
- Setup plan: scikit-learn is noted, installed with the project.
- Setup plan: install Cython>=3.0,<3.1 (listed in requirements.txt) on main and pr.
- Setup plan: install pytest>=7.0 (listed in requirements.txt) on main and pr.
- Setup plan: install setuptools>=68.0 (listed in requirements.txt) on main and pr.
- Setup plan: install ncls (listed in requirements.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.12
- rerun, setup problem: main install failed after 3 tries.
- Demo helper: setup failure already labelled; the probe was not rerun.

## Claims vs reality

No tests ran, so no claim could be checked.

## What changed in behavior

Not measured: install failed (1); see setup-main.log.

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

No probes ran: this record predates probes.

## Was the changed code exercised?

**Coverage: NOT MEASURED, record predates the coverage gate.** No coverage run exists for this record; nothing below is a measurement.

Coverage gate (python, confidence lower): coverage of the changed Python lines was NOT MEASURED (record predates the coverage gate: no coverage run exists for it, so this is not a measurement result).

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `6a5f2dfd7617` of the PR against main (source-pair route).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | install failed (1); see setup-main.log | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
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

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/macs-784 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/macs3-project/MACS/pull/784
```

## Evidence links

- [Pull request macs3-project/MACS#784](https://github.com/macs3-project/MACS/pull/784)
- [record.json](../../ops/runs/2026-10-22-check-0201/macs-784/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0201/macs-784/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0201/macs-784/setup-main.log)
- [git.log](../../ops/runs/2026-10-22-check-0201/macs-784/git.log)

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
