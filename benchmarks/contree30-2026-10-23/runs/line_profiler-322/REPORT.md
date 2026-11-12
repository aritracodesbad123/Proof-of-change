# Proof-of-Change daily ops run: line_profiler-322

Started 2026-10-24 07:16 IST, finished 2026-10-24 07:19 IST, wall time 2.8 min. Machine: local arm64 8 cpus. GitHub API calls: 1 (unauthenticated). Runner: ops/daily_run.py. Proof-of-Change commit: `863751e9580b866fe64247737975cb2e04e97215`.

## Recommendation: **APPROVE**

The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.

| PR | Title | Route | Verdict | Reason |
|---|---|---|---|---|
| [pyutils/line_profiler#322](https://github.com/pyutils/line_profiler/pull/322) | feat: Add reset_stats method to LineProfiler for resetting accumulated | source-pair | **could_not_verify** | could not verify: setup gap ubelt: ERROR collecting tests/test_explicit_profile.py ________________ | ModuleNotFoundError: No module named 'ubelt' |

## What went right

- 1 PR(s) selected and recorded; every record has machine_type and thread_env (6 thread vars pinned to 1).
- 1/1 tested PRs have 3 alternating runs per side.
- 1/1 records validate against the shared schema (harness/schema/observation.schema.json, record_kind pr_run).
- Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.
- Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).

## What went wrong

- pyutils/line_profiler#322: could not verify: could not verify: setup gap ubelt: ERROR collecting tests/test_explicit_profile.py ________________ | ModuleNotFoundError: No module named 'ubelt'

## How to fix

- pyutils/line_profiler#322: inspect setup/pytest logs in the run folder.

## Per PR

### pyutils/line_profiler#322: feat: Add reset_stats method to LineProfiler for resetting accumulated profiling data

- Link: https://github.com/pyutils/line_profiler/pull/322 | author `hidva` | head `550d1aa314ad` | updated 2025-07-18 05:53 IST
- Upstream CI: not checked (single-PR check) (checked on request with --pr)
- Route: source-pair
- Tested: main = main @ d3400d7f458b (base tip = first parent of the merge commit); PR = GitHub test merge commit f63dc8dfb092 (refs/pull/322/merge) of head 550d1aa314ad
- Tested main SHA: `d3400d7f458b` (main side that was tested (base-branch tip, or the merge-base when the pull request conflicts or the pinned head differs from the current head)); pull request base `61afe6e6624f` (pull request base (the commit the pull request was opened against; not necessarily the main side that was tested))
- Merge commit tested: `f63dc8dfb09266eed73a3c6b00dc2eef23e6a7a5` (refs/pull/322/merge; parents `d3400d7f458b`, `550d1aa314ad`)
- Touched package files: line_profiler/_line_profiler.pyx
- Tests run: tests/test_explicit_profile.py
- **Verdict: could_not_verify**: could not verify: setup gap ubelt: ERROR collecting tests/test_explicit_profile.py ________________ | ModuleNotFoundError: No module named 'ubelt'

#### Demo helper

These notes are background for the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing or fails to import, it looks up the cause, installs the fix on both sides and reruns that step, up to 3 tries.

- Setup check: GitHub token: missing.
- Setup check: Nebius token: present.
- Setup check: free memory could not be read.
- Setup check: free disk 38.2 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: line_profiler python setup install instructions https://github.com/pyutils/line_profiler site:github.com/pyutils/line_profiler
- Query: line_profiler python documentation install https://github.com/pyutils/line_profiler site:github.com/pyutils/line_profiler
- Query: line_profiler python install requirements https://pypi.org/project/line_profiler/ https://github.com/pyutils/line_profiler site:pypi.org
- Source: GitHub - pyutils/line_profiler: Line-by-line profiling for Python · GitHub — https://github.com/pyutils/line_profiler
- Source: pyutils/line_profiler at blog.easecloud.io — https://github.com/pyutils/line_profiler?ref=blog.easecloud.io
- Source: ModuleNotFoundError: No module named 'line_profiler._line_profiler' · Issue #50 · pyutils/line_profiler · GitHub — https://github.com/pyutils/line_profiler/issues/50
- Source: line_profiler/line_profiler/_line_profiler.pyx at main · pyutils/line_profiler · GitHub — https://github.com/pyutils/line_profiler/blob/main/line_profiler/_line_profiler.pyx
- Source: line_profiler/LICENSE_Python.txt at main · pyutils/line_profiler · GitHub — https://github.com/pyutils/line_profiler/blob/main/LICENSE_Python.txt
- Setup plan: the same packages on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.10
- Setup plan: Python rule: one Python version is used on both sides: the lowest version that meets the requirements of both main and the pull request; if none meets both, the check stops as a setup problem and records both.
- Setup plan: refused ubelt: not listed by the project and not a link-back suggestion
- Before rerun: could_not_verify: no test actually ran on either side: 0 tests ran; 0 new test(s) pass, 0 unchanged; 1 test module(s) fail to load on both sides (tests.test_explicit_profile), so their tests did not run; probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-p2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count
- After rerun: not rerun. could not verify: setup gap ubelt: ERROR collecting tests/test_explicit_profile.py ________________ | ModuleNotFoundError: No module named 'ubelt'
- Coverage gate (compiled): compiled code changed (line_profiler/_line_profiler.pyx); coverage.py cannot see compiled code and the PR adds or changes no test for it; confidence normal
- Exit codes: pytest exit 1; no identical pre-existing failures
- Runs: main#1 exit=1 2.2s 1 error in 0.37s; pr#1 exit=1 2.2s 1 error in 0.38s; main#2 exit=1 2.1s 1 error in 0.36s; pr#2 exit=1 2.2s 1 error in 0.37s; main#3 exit=1 2.2s 1 error in 0.37s; pr#3 exit=1 2.2s 1 error in 0.39s
- Duration: 167.8s total (tests 13.1s); logs: `line_profiler-322/`

## Skipped while selecting


## Limits of this run

- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.
- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch applies the PR diff on top of it, so a clean apply is required.
- Tests ran on the local machine and were not network-isolated.

Self-check: the report matches the run records.
