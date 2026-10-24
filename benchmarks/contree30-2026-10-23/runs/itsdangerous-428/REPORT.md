# Proof-of-Change daily ops run: itsdangerous-428

Started 2026-10-23 11:24 IST, finished 2026-10-23 11:42 IST, wall time 17.3 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [pallets/itsdangerous#428](https://github.com/pallets/itsdangerous/pull/428) | require padding when decoding base64 on Python 3.15+ | source-pair | **needs_attention** | probe: 6 observation(s) need attention: decode_no_pad_exception does not differ although the claim says it does (C1); decode_no_pad_result does not differ although the claim says it does (C1); decode_ |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 tested PRs have 3 alternating runs per side.
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- pallets/itsdangerous#428: needs attention: probe: 6 observation(s) need attention: decode_no_pad_exception does not differ although the claim says it does (C1); decode_no_pad_result does not differ although the claim says it does (C1); decode_pad_exception does not differ although the claim says it does (C1); decode_pad_result does not differ although the claim says it does (C1); probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change; probe model-p2 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change; probe model-p3 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change; tests: 8 test(s) ran on main, 8 on the PR; 0 new test(s) pass, 8 unchanged (a finding about the PR, not a run failure)

## How to fix

- pallets/itsdangerous#428: a human should read the differing tests in record.json/pytest logs.

## Per PR

### pallets/itsdangerous#428: require padding when decoding base64 on Python 3.15+

- Link: https://github.com/pallets/itsdangerous/pull/428 | author `mgorny` | head `d9f3b250e0ca` | updated 2026-08-06 00:00 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ 672971d66a2e (base tip = first parent of the merge commit); PR = GitHub test merge commit 08c336cc549e (refs/pull/428/merge) of head d9f3b250e0ca
- Tested main SHA: `672971d66a2e` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `672971d66a2e` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Merge commit tested: `08c336cc549ea319f92abf254667c8e6c7789f9f` (refs/pull/428/merge; parents `672971d66a2e`, `d9f3b250e0ca`)
- Touched package files: src/itsdangerous/encoding.py
- Tests run: tests/test_itsdangerous/test_encoding.py
- **Verdict: needs_attention**: probe: 6 observation(s) need attention: decode_no_pad_exception does not differ although the claim says it does (C1); decode_no_pad_result does not differ although the claim says it does (C1); decode_pad_exception does not differ although the claim says it does (C1); decode_pad_result does not differ although the claim says it does (C1); probe model-p1 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change; probe model-p2 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change; probe model-p3 has no measured line coverage (Contree-only check: probe coverage needs a local side); it does not count as covering the change; tests: 8 test(s) ran on main, 8 on the PR; 0 new test(s) pass, 8 unchanged

#### Demo helper

These notes are background for the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: missing.
- Setup check: Nebius token: present.
- Setup check: free memory could not be read.
- Setup check: free disk 37.4 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 3 results
- Query: itsdangerous python setup install instructions https://github.com/pallets/itsdangerous site:github.com/pallets/itsdangerous
- Query: itsdangerous python documentation install https://github.com/pallets/itsdangerous site:github.com/pallets/itsdangerous
- Query: itsdangerous python install requirements https://pypi.org/project/itsdangerous/ https://github.com/pallets/itsdangerous site:pypi.org
- Source: Releases · pallets/itsdangerous · GitHub — https://github.com/pallets/itsdangerous/releases
- Source: serializer.py - pallets/itsdangerous — https://github.com/pallets/itsdangerous/blob/main/src/itsdangerous/serializer.py
- Source: TimestampSigner writes local-time timestamps and reads ... — https://github.com/pallets/itsdangerous/issues/137
- Setup plan: the same packages on main and pr.
- Setup plan: install freezegun (listed in the tests extra) on main and pr.
- Setup plan: install pytest (listed in the tests extra) on main and pr.
- Setup plan: install ruff (listed in a dependency group) on main and pr.
- Setup plan: install tox (listed in a dependency group) on main and pr.
- Setup plan: install tox-uv (listed in a dependency group) on main and pr.
- Setup plan: install pallets-sphinx-themes (listed in a dependency group) on main and pr.
- Setup plan: install sphinx (listed in a dependency group) on main and pr.
- Setup plan: install sphinxcontrib-log-cabinet (listed in a dependency group) on main and pr.
- Setup plan: install sphinx-autobuild (listed in a dependency group) on main and pr.
- Setup plan: install gha-update ; python_full_version >= '3.12' (listed in a dependency group) on main and pr.
- Setup plan: install pre-commit (listed in a dependency group) on main and pr.
- Setup plan: install pre-commit-uv (listed in a dependency group) on main and pr.
- Setup plan: install mypy (listed in a dependency group) on main and pr.
- Setup plan: install pyright (listed in a dependency group) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.10, >=3.8
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Coverage gate (python): 3 of 4 changed executable line(s) ran (75%); confidence normal
- Exit codes: all runs exited 0
- Runs: main#1 exit=0 2.5s 8 passed in 0.53s; pr#1 exit=0 2.9s 8 passed in 0.52s; main#2 exit=0 3.8s 8 passed in 0.52s; pr#2 exit=0 2.6s 8 passed in 0.52s; main#3 exit=0 2.9s 8 passed in 0.54s; pr#3 exit=0 2.6s 8 passed in 0.52s
- Duration: 1040.9s total (tests 17.3s); logs: `itsdangerous-428/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
