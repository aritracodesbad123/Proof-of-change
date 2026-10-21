# Reviewer report: pahaz/sshtunnel#304: Migrate to PEP518

Run `sshtunnel-304`, tested 2026-10-21 19:51 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `02a68eea38919fef2e1b537c3bf5a64bd7c771b5`. Report generated 2026-10-21 19:52 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Migrate to PEP518 ([pahaz/sshtunnel#304](https://github.com/pahaz/sshtunnel/pull/304)).
- **What we observed:** no tests could be mapped to the touched files.
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

The PR titled "Migrate to PEP518" resulted in a verdict of "could_not_verify" because no tests could be mapped to the touched files; the baseline used was "full".

Quoted from the record: `Migrate to PEP518`; `could_not_verify`; `no tests could be mapped to the touched files`; `full`

Model summary is advisory; the code verdict above is authoritative.

### Agent swarm (advisory)

| Role | Model | Status | Notes |
|---|---|---|---|
| judge | nvidia/Nemotron-3-Ultra-550b-a55b | ok | - |
| helper | nvidia/Nemotron-3_5-Lightning | ok | Ignore README changes if pyproject.toml is untouched; Ignore whitespace-only changes in pyproject.toml [build-system]; Install build backend: pip install build wheel for local PEP518 verification |
| summary | nvidia/nemotron-3-super-120b-a12b | ok | - |

judge/helper/summary are advisory; code owns the verdict

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.3 GB (of 15.6 GB).
- Setup check: free disk 98.1 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 4 results
- Query: sshtunnel python setup install instructions https://github.com/pahaz/sshtunnel site:github.com/pahaz/sshtunnel
- Query: sshtunnel python documentation install https://github.com/pahaz/sshtunnel site:github.com/pahaz/sshtunnel
- Query: sshtunnel python install requirements https://pypi.org/project/sshtunnel/ https://github.com/pahaz/sshtunnel site:pypi.org
- Source: sshtunnel · PyPI — https://pypi.org/project/sshtunnel/
- Source: GitHub - pahaz/sshtunnel: SSH tunnels to remote server. · GitHub — https://github.com/pahaz/sshtunnel
- Source: sshtunnel/sshtunnel.py at master · pahaz/sshtunnel · GitHub — https://github.com/pahaz/sshtunnel/blob/master/sshtunnel.py
- Source: psycopg2 conn.poll() hangs when used with sshtunnel · Issue #135 · pahaz/sshtunnel · GitHub — https://github.com/pahaz/sshtunnel/issues/135
- Setup plan: the same packages on main and pr.
- Setup plan: paramiko is noted, installed with the project.
- Setup plan: install docutils (listed in requirements.txt) on main and pr.
- Setup plan: install sphinx (listed in requirements.txt) on main and pr.
- Setup plan: install sphinxcontrib-napoleon (listed in requirements.txt) on main and pr.
- Setup plan: install bashtest (listed in requirements-syntax.txt) on main and pr.
- Setup plan: install check-manifest (listed in requirements-syntax.txt) on main and pr.
- Setup plan: install flake8 (listed in requirements-syntax.txt) on main and pr.
- Setup plan: install mccabe (listed in requirements-syntax.txt) on main and pr.
- Setup plan: install pygments (listed in requirements-syntax.txt) on main and pr.
- Setup plan: install readme (listed in requirements-syntax.txt) on main and pr.
- Setup plan: install twine (listed in requirements-syntax.txt) on main and pr.
- Setup plan: install coveralls (listed in requirements.txt) on main and pr.
- Setup plan: install mock (listed in requirements.txt) on main and pr.
- Setup plan: install pytest (listed in requirements.txt) on main and pr.
- Setup plan: install pytest-cov (listed in requirements.txt) on main and pr.
- Setup plan: install pytest-xdist (listed in requirements.txt) on main and pr.
- Setup plan: install bleach<5.0.0 (listed in requirements.txt) on main and pr.
- Setup plan: install readme-renderer<25.0; python_version == '3.4' (listed in requirements.txt) on main and pr.
- Setup plan: install importlib-metadata==1.7.0; python_version == '3.5' (listed in requirements.txt) on main and pr.
- Setup plan: install tox>=1.8.1 (listed in the test extra) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=2.7
- Installed docutils 0.22.4 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed sphinx 9.1.1 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed sphinxcontrib-napoleon 0.7 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed bashtest 0.0.8 from requirements-syntax.txt (listed in requirements-syntax.txt) on main and pr.
- Installed check-manifest 0.51 from requirements-syntax.txt (listed in requirements-syntax.txt) on main and pr.
- Installed flake8 7.4.1 from requirements-syntax.txt (listed in requirements-syntax.txt) on main and pr.
- Installed mccabe 0.7.0 from requirements-syntax.txt (listed in requirements-syntax.txt) on main and pr.
- Installed pygments 2.21.0 from requirements-syntax.txt (listed in requirements-syntax.txt) on main and pr.
- Installed readme 0.7.1 from requirements-syntax.txt (listed in requirements-syntax.txt) on main and pr.
- Installed twine 7.0.0 from requirements-syntax.txt (listed in requirements-syntax.txt) on main and pr.
- Installed coveralls 4.1.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed mock 5.2.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed pytest 9.1.1 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed pytest-cov 7.1.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed pytest-xdist 3.8.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed bleach 4.1.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed readme-renderer 46.0 from requirements.txt (listed in requirements.txt) on main and pr.
- Installed importlib-metadata  from requirements.txt (listed in requirements.txt) on main and pr.
- Installed tox 4.67.1 from pyproject (listed in the test extra) on main and pr.

### Background (related public bug reports, not used for the verdict)

1. "Issues · pahaz/sshtunnel · GitHub"
   https://github.com/pahaz/sshtunnel/issues
   "pahaz/sshtunnel#294 · opened on Nov 6, 2024 ### Transfer the local port to remote server pahaz/sshtunnel#293 · opened on Oct 29, 2024 ### Using sshtunnel on Mac? pahaz/sshtunnel#290 · opened on Mar 20, 2024 1 ### SSH Tunnel Connection Drop..."
2. "Welcome to sshtunnel’s documentation! — sshtunnel 0.4.0 documentation"
   https://sshtunnel.readthedocs.io
   "v.0.0.4.1 (Pahaz) : + fix CLI issues #13 (Pahaz) v.0.0.4 (Pahaz) : + daemon mode by default for all threads (JM Fernández, Pahaz) - incompatible + move `make_ssh_forward_server` to `SSHTunnelForwarder.make_ssh_forward_server` (Pahaz, JM Fer..."
3. "python-sshtunnel(1) — Arch manual pages"
   https://man.archlinux.org/man/python-sshtunnel.1.en
   "daemon mode by default for all threads (JM Fernández , Pahaz ) - incompatible move make\_ssh\_forward\_s...

## Claims vs reality

No tests ran, so no claim could be checked.

## What changed in behavior

Not measured: no tests could be mapped to the touched files.

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

No probe ran for this PR (no fixed probe in probes/<owner>/<repo>/<pr>.py and no model-written or differential probe), so only the tests were compared.

## Was the changed code exercised?

**Coverage: not needed** (no changed Python lines).

Coverage gate (no-executable-change, confidence normal): no executable code changed (docs, tests or config only), so there was nothing to cover.

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `6ca35a37971a` of the PR against main (source-pair route).
- Changed code was exercised (coverage gate): no executable code changed (docs, tests or config only), so there was nothing to cover.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | no tests could be mapped to the touched files | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| Changed code was exercised (coverage gate) | 🟢 **PASS** | no executable code changed (docs, tests or config only), so there was nothing to cover |
| Probes ran on both sides | ⚪ **SKIP** | no probe for this PR |
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

**Decision recorded:** none yet. To record one, run `make decide REPORT=./report/sshtunnel-304 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/pahaz/sshtunnel/pull/304
```

## Evidence links

- [Pull request pahaz/sshtunnel#304](https://github.com/pahaz/sshtunnel/pull/304)
- [record.json](../../ops/runs/2026-10-21-check-1951/sshtunnel-304/record.json)
- [pr.diff](../../ops/runs/2026-10-21-check-1951/sshtunnel-304/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-21-check-1951/sshtunnel-304/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-21-check-1951/sshtunnel-304/setup-pr.log)
- [git.log](../../ops/runs/2026-10-21-check-1951/sshtunnel-304/git.log)

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
