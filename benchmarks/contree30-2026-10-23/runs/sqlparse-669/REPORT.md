# Proof-of-Change daily ops run: sqlparse-669

Started 2026-10-23 15:16 IST, finished 2026-10-23 15:19 IST, wall time 2.4 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [andialbrecht/sqlparse#669](https://github.com/andialbrecht/sqlparse/pull/669) | Strip last statement when it only contains comment | source-pair | **needs_attention** | probe: 10 observation(s) need attention: only_comment_last differs and no claim covers it; only_comment_len differs and no claim covers it; select1_block_last differs and no claim covers it; select1_b |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- andialbrecht/sqlparse#669: needs attention: probe: 10 observation(s) need attention: only_comment_last differs and no claim covers it; only_comment_len differs and no claim covers it; select1_block_last differs and no claim covers it; select1_block_len differs and no claim covers it; rejected: claim pattern(s) C1 match none of this probe's observation names, so the probe is not counted; tests: no tests could be mapped to the touched files (a finding about the PR, not a run failure)

## How to fix

- andialbrecht/sqlparse#669: a human should read the differing tests in record.json/pytest logs.

## Re-runs

Earlier attempts of this run date are kept under `superseded/attempt-N/` (records, logs, NOTE.md). The day's PR selection is frozen: this attempt re-tests every PR that any earlier attempt selected.

- **attempt-1**: attempt-1: superseded at 2026-10-23 15:16 IST. Selected 1 PR(s), 1 record(s).

Dropped between attempts (selected by an attempt, absent from the next attempt that selected PRs):

- none

| PR | attempt-1 | this run |
|---|---|---|
| andialbrecht/sqlparse#669 | could_not_verify | needs_attention |

## Per PR

### andialbrecht/sqlparse#669: Strip last statement when it only contains comment

- Link: https://github.com/andialbrecht/sqlparse/pull/669 | author `botenvouwer` | head `e980a615eb73` | updated 2023-01-02 17:48 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = master @ 83e5381fc320 (merge-base with the PR head); PR = PR head e980a615eb73
- Tested main SHA: `83e5381fc320` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `83e5381fc320` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Touched package files: sqlparse/__init__.py
- Tests run: -
- **Verdict: needs_attention**: probe: 10 observation(s) need attention: only_comment_last differs and no claim covers it; only_comment_len differs and no claim covers it; select1_block_last differs and no claim covers it; select1_block_len differs and no claim covers it; rejected: claim pattern(s) C1 match none of this probe's observation names, so the probe is not counted; tests: no tests could be mapped to the touched files

#### Demo helper

These notes are background for the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: missing.
- Setup check: Nebius token: present.
- Setup check: free memory could not be read.
- Setup check: free disk 37.3 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: sqlparse python setup install instructions https://github.com/andialbrecht/sqlparse site:github.com/andialbrecht/sqlparse
- Query: sqlparse python documentation install https://github.com/andialbrecht/sqlparse site:github.com/andialbrecht/sqlparse
- Query: sqlparse python install requirements https://pypi.org/project/sqlparse/ https://github.com/andialbrecht/sqlparse site:pypi.org
- Source: GitHub - andialbrecht/sqlparse: A non-validating SQL parser module for Python · GitHub — https://github.com/andialbrecht/sqlparse
- Source: sqlparse/.github/workflows/python-app.yml at master · andialbrecht/sqlparse · GitHub — https://github.com/andialbrecht/sqlparse/blob/master/.github/workflows/python-app.yml
- Source: sqlparse/Makefile at master · andialbrecht/sqlparse · GitHub — https://github.com/andialbrecht/sqlparse/blob/master/Makefile
- Source: sqlparse/CHANGELOG at master · andialbrecht/sqlparse · GitHub — https://github.com/andialbrecht/sqlparse/blob/master/CHANGELOG
- Source: sqlparse/.readthedocs.yaml at master · andialbrecht/sqlparse · GitHub — https://github.com/andialbrecht/sqlparse/blob/master/.readthedocs.yaml
- Setup plan: the same packages on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.5, >=3.10
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): coverage of the changed Python lines was NOT MEASURED (Contree mode: coverage runs only inside Contree, and it was not run there); confidence lower
- Runs: 0 per side (planned 3)
- Duration: 141.4s total (tests 0s); logs: `sqlparse-669/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
