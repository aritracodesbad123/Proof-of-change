# Proof-of-Change daily ops run: prettytable-223

Started 2026-10-24 07:11 IST, finished 2026-10-24 07:14 IST, wall time 2.8 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [prettytable/prettytable#223](https://github.com/prettytable/prettytable/pull/223) | Refactor old %-formatting to use format() builtin | source-pair | **needs_attention** | 1 new test(s) fail on the PR; 24 test(s) removed on the PR side; 111 test(s) ran on main, 88 on the PR; 0 new test(s) pass, 82 unchanged; 5 test failure(s) pre-existing and identical on both sides; pr |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 tested PRs have 3 alternating runs per side.
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- prettytable/prettytable#223: needs attention: 1 new test(s) fail on the PR; 24 test(s) removed on the PR side; 111 test(s) ran on main, 88 on the PR; 0 new test(s) pass, 82 unchanged; 5 test failure(s) pre-existing and identical on both sides; probe: 1 observation(s) need attention: probe_c1_int_format_error does not differ although the claim says it does (C1); probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change; probe model-p2 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change (a finding about the PR, not a run failure)

## How to fix

- prettytable/prettytable#223: a human should read the differing tests in record.json/pytest logs.

## Per PR

### prettytable/prettytable#223: Refactor old %-formatting to use format() builtin

- Link: https://github.com/prettytable/prettytable/pull/223 | author `mwtoews` | head `b0a2362c2989` | updated 2023-01-16 17:34 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ 32e788f655c4 (merge-base with the PR head); PR = PR head b0a2362c2989
- Tested main SHA: `32e788f655c4` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `32e788f655c4` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Test extras installed on both sides: ['pytest-lazy-fixture']; optional test deps: -
- Touched package files: src/prettytable/prettytable.py
- Tests run: tests/test_prettytable.py
- **Verdict: needs_attention**: 1 new test(s) fail on the PR; 24 test(s) removed on the PR side; 111 test(s) ran on main, 88 on the PR; 0 new test(s) pass, 82 unchanged; 5 test failure(s) pre-existing and identical on both sides; probe: 1 observation(s) need attention: probe_c1_int_format_error does not differ although the claim says it does (C1); probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change; probe model-p2 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change

#### Demo helper

These notes are background for the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: missing.
- Setup check: Nebius token: present.
- Setup check: free memory could not be read.
- Setup check: free disk 38.9 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: prettytable python setup install instructions https://github.com/prettytable/prettytable site:github.com/prettytable/prettytable
- Query: prettytable python documentation install https://github.com/prettytable/prettytable site:github.com/prettytable/prettytable
- Query: prettytable python install requirements https://pypi.org/project/prettytable/ https://github.com/prettytable/prettytable site:pypi.org
- Source: prettytable · PyPI — https://pypi.org/project/prettytable/
- Source: prettytable/CHANGELOG.md at main · prettytable/prettytable · GitHub — https://github.com/prettytable/prettytable/blob/main/CHANGELOG.md
- Source: GitHub - prettytable/prettytable: Display tabular data in a visually appealing ASCII table format · GitHub — https://github.com/prettytable/prettytable
- Source: prettytable/.gitignore at main — https://github.com/prettytable/prettytable/blob/main/.gitignore
- Source: Wrap strings to newline when maximum width of column is reached · Issue #130 · prettytable/prettytable · GitHub — https://github.com/prettytable/prettytable/issues/130
- Setup plan: the PR changes install docs (README.md); setup was read from main's copy and applied the same on both sides.
- Setup plan: the same packages on main and pr.
- Setup plan: importlib-metadata is noted, installed with the project.
- Setup plan: wcwidth is noted, installed with the project.
- Setup plan: install pytest (listed in the tests extra) on main and pr.
- Setup plan: install pytest-cov (listed in the tests extra) on main and pr.
- Setup plan: install pytest-lazy-fixture (listed in the tests extra) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.7, >=3.10
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): 22 of 24 changed executable line(s) ran (92%); confidence normal
  - new_tests_failing: tests.test_prettytable::TestBasic
  - removed_tests: tests.test_prettytable.TestBasic::test_all_lengths_equal, tests.test_prettytable.TestBasic::test_all_lengths_equal_from_csv, tests.test_prettytable.TestBasic::test_all_lengths_equal_from_db, tests.test_prettytable.TestBasic::test_all_lengths_equal_with_float_format, tests.test_prettytable.TestBasic::test_all_lengths_equal_with_hrules_all (+19)
  - `tests.test_prettytable::TestBasic`: `collection failure`
- Exit codes: pytest exit 1; 5 failure(s)/error(s) pre-existing and identical on both sides
- Runs: main#1 exit=1 2.9s /usr/local/lib/python3.12/site-packages/pytest_lazyfixture.p; pr#1 exit=1 3.6s     return self._i; main#2 exit=1 3.5s /usr/local/lib/python3.12/site-packages/pytest_lazyfixture.p; pr#2 exit=1 3.0s     return self._i; main#3 exit=1 3.0s /usr/local/lib/python3.12/site-packages/pytest_lazyfixture.p; pr#3 exit=1 3.2s     return self._i
- Duration: 170.6s total (tests 19.2s); logs: `prettytable-223/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
