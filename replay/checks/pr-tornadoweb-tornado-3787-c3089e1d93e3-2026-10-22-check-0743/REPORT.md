# Reviewer report: tornadoweb/tornado#3787: web: Bound the static version cache, update docs

Run `tornado-3787`, tested 2026-10-22 07:43 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 07:43 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** web: Bound the static version cache, update docs ([tornadoweb/tornado#3787](https://github.com/tornadoweb/tornado/pull/3787)).
- **What we observed:** install failed (1); see setup-main.log.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.3 GB (of 15.6 GB).
- Setup check: free disk 92.3 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 7 results
- Query: tornado python setup install instructions https://github.com/tornadoweb/tornado site:github.com/tornadoweb/tornado
- Query: tornado python documentation install https://github.com/tornadoweb/tornado site:github.com/tornadoweb/tornado
- Query: tornado python install requirements https://pypi.org/project/tornado/ https://github.com/tornadoweb/tornado site:pypi.org
- Source: tornado · PyPI — https://pypi.org/project/tornado/
- Source: tornado/maint/vm/windows/bootstrap.py at master — https://github.com/tornadoweb/tornado/blob/master/maint/vm/windows/bootstrap.py
- Source: Support for free-threaded CPython · Issue #3501 · tornadoweb/tornado · GitHub — https://github.com/tornadoweb/tornado/issues/3501
- Source: Performance issues when use websocket upload binary files · Issue #3007 · tornadoweb/tornado · GitHub — https://github.com/tornadoweb/tornado/issues/3007
- Source: GitHub - tornadoweb/tornado: Tornado is a Python web framework and asynchronous networking library, originally developed at FriendFeed. · GitHub — https://github.com/tornadoweb/tornado
- Source: tornado/.github/workflows/build.yml at 657d5939cccbc1fcedb75c92cd1b427e9fd974b3 · tornadoweb/tornado · GitHub — https://github.com/tornadoweb/tornado/blob/HEAD/.github/workflows/build.yml
- Source: tornado/.github/workflows/build.yml at 7d6465056ceb7a054b3f64cf1c18271753b10482 · tornadoweb/tornado · GitHub — https://github.com/tornadoweb/tornado/blob/7d6465056ceb7a054b3f64cf1c18271753b10482/.github/workflows/build.yml
- Setup plan: the same packages on main and pr.
- Setup plan: install alabaster==1.0.0 (listed in requirements.txt) on main and pr.
- Setup plan: install ast-serialize==0.11.2 (listed in requirements.txt) on main and pr.
- Setup plan: install babel==2.18.0 (listed in requirements.txt) on main and pr.
- Setup plan: install black==26.5.1 (listed in requirements.txt) on main and pr.
- Setup plan: install build==1.6.1 (listed in requirements.txt) on main and pr.
- Setup plan: install cachetools==7.1.8 (listed in requirements.txt) on main and pr.
- Setup plan: install certifi==2026.7.22 (listed in requirements.txt) on main and pr.
- Setup plan: install charset-normalizer==3.5.1 (listed in requirements.txt) on main and pr.
- Setup plan: install click==8.5.0 (listed in requirements.txt) on main and pr.
- Setup plan: install colorama==0.4.6 (listed in requirements.txt) on main and pr.
- Setup plan: install distlib==0.4.3 (listed in requirements.txt) on main and pr.
- Setup plan: install docutils==0.22.4 (listed in requirements.txt) on main and pr.
- Setup plan: install filelock==3.32.7 (listed in requirements.txt) on main and pr.
- Setup plan: install flake8==7.3.0 (listed in requirements.txt) on main and pr.
- Setup plan: install idna==3.19 (listed in requirements.txt) on main and pr.
- Setup plan: install imagesize==2.0.1 (listed in requirements.txt) on main and pr.
- Setup plan: install jinja2==3.1.6 (listed in requirements.txt) on main and pr.
- Setup plan: install librt==0.15.0 (listed in requirements.txt) on main and pr.
- Setup plan: install markupsafe==3.0.3 (listed in requirements.txt) on main and pr.
- Setup plan: install mccabe==0.7.0 (listed in requirements.txt) on main and pr.
- Setup plan: install mypy==2.3.1 (listed in requirements.txt) on main and pr.
- Setup plan: install mypy-extensions==1.1.0 (listed in requirements.txt) on main and pr.
- Setup plan: install packaging==26.3 (listed in requirements.txt) on main and pr.
- Setup plan: install pathspec==1.1.1 (listed in requirements.txt) on main and pr.
- Setup plan: install pip-tools==7.6.1 (listed in requirements.txt) on main and pr.
- Setup plan: install platformdirs==4.11.9 (listed in requirements.txt) on main and pr.
- Setup plan: install pluggy==1.6.0 (listed in requirements.txt) on main and pr.
- Setup plan: install pycodestyle==2.14.0 (listed in requirements.txt) on main and pr.
- Setup plan: install pyflakes==3.4.0 (listed in requirements.txt) on main and pr.
- Setup plan: install pygments==2.21.0 (listed in requirements.txt) on main and pr.
- Setup plan: install pyproject-api==1.11.1 (listed in requirements.txt) on main and pr.
- Setup plan: install pyproject-hooks==1.3.3 (listed in requirements.txt) on main and pr.
- Setup plan: install python-discovery==1.6.0 (listed in requirements.txt) on main and pr.
- Setup plan: install pytokens==0.4.1 (listed in requirements.txt) on main and pr.
- Setup plan: install requests==2.34.2 (listed in requirements.txt) on main and pr.
- Setup plan: install roman-numerals==4.1.0 (listed in requirements.txt) on main and pr.
- Setup plan: install snowballstemmer==3.1.1 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinx==9.0.4 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinx-rtd-theme==3.1.0 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinxcontrib-applehelp==2.0.0 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinxcontrib-devhelp==2.0.0 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinxcontrib-htmlhelp==2.1.0 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinxcontrib-jquery==4.1 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinxcontrib-jsmath==1.0.1 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinxcontrib-qthelp==2.0.0 (listed in requirements.txt) on main and pr.
- Setup plan: install sphinxcontrib-serializinghtml==2.0.0 (listed in requirements.txt) on main and pr.
- Setup plan: install tomli-w==1.2.0 (listed in requirements.txt) on main and pr.
- Setup plan: install tox==4.61.4 (listed in requirements.txt) on main and pr.
- Setup plan: install types-pycurl==7.47.0.20260703 (listed in requirements.txt) on main and pr.
- Setup plan: install typing-extensions==4.16.0 (listed in requirements.txt) on main and pr.
- Setup plan: install urllib3==2.8.0 (listed in requirements.txt) on main and pr.
- Setup plan: install virtualenv==21.7.13 (listed in requirements.txt) on main and pr.
- Setup plan: install wheel==0.48.0 (listed in requirements.txt) on main and pr.
- Setup plan: install aiopg (listed in requirements.txt) on main and pr.
- Setup plan: install bcrypt (listed in requirements.txt) on main and pr.
- Setup plan: install markdown (listed in requirements.txt) on main and pr.
- Setup plan: install psycopg2 (listed in requirements.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >= 3.11, >=3.11
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

- Tested `c3089e1d93e3` of the PR against main (source-pair route).
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

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/tornado-3787 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/tornadoweb/tornado/pull/3787
```

## Evidence links

- [Pull request tornadoweb/tornado#3787](https://github.com/tornadoweb/tornado/pull/3787)
- [record.json](../../ops/runs/2026-10-22-check-0743/tornado-3787/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0743/tornado-3787/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0743/tornado-3787/setup-main.log)
- [git.log](../../ops/runs/2026-10-22-check-0743/tornado-3787/git.log)

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
