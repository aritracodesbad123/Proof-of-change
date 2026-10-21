# Reviewer report: home-assistant-libs/pychromecast#1300: Expose multizone playback session info

Run `pychromecast-1300`, tested 2026-10-21 19:31 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `5492834eef22efd122549356c73d26b3d0ae040a`. Report generated 2026-10-21 19:35 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Expose multizone playback session info ([home-assistant-libs/pychromecast#1300](https://github.com/home-assistant-libs/pychromecast/pull/1300)).
- **What we observed:** could not verify: claim(s) C1, C2, C3, C4 (+2 more) expect a difference but no observation matches (1 test(s) ran on main, 6 on the PR; 5 new test(s) pass, 1 unchanged; probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count).
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

The PR titled "Expose multizone playback session info" has a verdict of "could_not_verify". The reason given is "could not verify: claim(s) C1, C2, C3, C4 (+2 more) expect a difference but no observation matches (1 test(s) ran on main, 6 on the PR; 5 new test(s) pass, 1 unchanged; probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count". The baseline is "full" and the probe summary notes "the probe crashed or printed no parsed output on every main-side run".

Quoted from the record: `Expose multizone playback session info`; `could_not_verify`; `could not verify: claim(s) C1, C2, C3, C4 (+2 more) expect a difference but no observation matches (1 test(s) ran on main, 6 on the PR; 5 new test(s) pass, 1 unchanged; probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count`; `full`; `the probe crashed or printed no parsed output on every main-side run`

Model summary is advisory; the code verdict above is authoritative.

### Agent swarm (advisory)

| Role | Model | Status | Notes |
|---|---|---|---|
| judge | nvidia/Nemotron-3-Ultra-550b-a55b | ok | 1 labels |
| helper | nvidia/Nemotron-3_5-Lightning | ok | probe model-p1 crash: likely missing dependency or path issue; add to ignored_noise if reproducible; claims C1-C6 expect difference but no observation matches; mark as known-noise if stable across runs; 5 new passing tests confirm positive signal; no action needed |
| summary | nvidia/nemotron-3-super-120b-a12b | ok | - |

judge/helper/summary are advisory; code owns the verdict

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 5.8 GB (of 15.6 GB).
- Setup check: free disk 98.1 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: pychromecast python setup install instructions https://github.com/home-assistant-libs/pychromecast site:github.com/home-assistant-libs/pychromecast
- Query: pychromecast python documentation install https://github.com/home-assistant-libs/pychromecast site:github.com/home-assistant-libs/pychromecast
- Query: pychromecast python install requirements https://pypi.org/project/pychromecast/ https://github.com/home-assistant-libs/pychromecast site:pypi.org
- Source: PyChromecast · PyPI — https://pypi.org/project/pychromecast/
- Source: GitHub - home-assistant-libs/pychromecast: Library for Python 3 to communicate with the Google Chromecast. · GitHub — https://github.com/home-assistant-libs/pychromecast
- Source: pychromecast/pychromecast/socket_client.py at master · home-assistant-libs/pychromecast · GitHub — https://github.com/home-assistant-libs/pychromecast/blob/master/pychromecast/socket_client.py
- Source: pychromecast/examples/media_enqueue.py at master · home-assistant-libs/pychromecast · GitHub — https://github.com/home-assistant-libs/pychromecast/blob/master/examples/media_enqueue.py
- Source: "[WinError 10049] The requested address is not valid in its ... — https://github.com/home-assistant-libs/pychromecast/issues/483
- Setup plan: the same packages on main and pr.
- Setup plan: protobuf is noted, installed with the project.
- Setup plan: zeroconf is noted, installed with the project.
- Setup plan: casttube is noted, installed with the project.
- Setup plan: install beautifulsoup4==4.15.0 (listed in requirements-test.txt) on main and pr.
- Setup plan: install ruff==0.17.1 (listed in requirements-test.txt) on main and pr.
- Setup plan: install mypy==2.4.0 (listed in requirements-test.txt) on main and pr.
- Setup plan: install PlexAPI==4.17.2 (listed in requirements-test.txt) on main and pr.
- Setup plan: install pylint==4.1.3 (listed in requirements-test.txt) on main and pr.
- Setup plan: install pytest==9.1.1 (listed in requirements-test.txt) on main and pr.
- Setup plan: install rstcheck==6.3.0 (listed in requirements-test.txt) on main and pr.
- Setup plan: install types-beautifulsoup4==4.12.0.20250516 (listed in requirements-test.txt) on main and pr.
- Setup plan: install types-html5lib==1.1.11.20260518 (listed in requirements-test.txt) on main and pr.
- Setup plan: install types-protobuf==7.35.1.20260906 (listed in requirements-test.txt) on main and pr.
- Setup plan: install types-requests==2.33.0.20261006 (listed in requirements-test.txt) on main and pr.
- Setup plan: install yle-dl==20240927 (listed in requirements-test.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.11.0
- Installed beautifulsoup4 4.15.0 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed ruff 0.17.1 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed mypy 2.4.0 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed PlexAPI 4.17.2 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed pylint 4.1.3 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed pytest 9.1.1 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed rstcheck 6.3.0 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed types-beautifulsoup4 4.12.0.20250516 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed types-html5lib 1.1.11.20260518 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed types-protobuf 7.35.1.20260906 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed types-requests 2.33.0.20261006 from requirements-test.txt (listed in requirements-test.txt) on main and pr.
- Installed yle-dl 20240927 from requirements-test.txt (listed in requirements-test.txt) on main and pr.

### Background (related public bug reports, not used for the verdict)

1. "Issues · home-assistant-libs/pychromecast · GitHub"
   https://github.com/home-assistant-libs/pychromecast/issues
   "home-assistant-libs/pychromecast#1059 · opened on Apr 28, 2025 ### Fields in `media.metadata` (artist, title etc) never get cleared in `MediaStatus` and can report wrong/stale info. home-assistant-libs/pychromecast#1018 · opened on Feb 3, 2..."
2. "GitHub - home-assistant-libs/pychromecast: Library for Python 3 to communicate with the Google Chromecast. · GitHub"
   https://github.com/home-assistant-libs/pychromecast
   "namespaces ='urn:x-cast:com.google.cast.player.message''urn:x-cast:com.google.cast.media' session_id ='CCA39713-9A4F-34A6-A8BF-5D97BE7ECA5C' transport_id ='web-9' status_text = '' >> mc = cast media_controller >> mc play_media' >> mc block_..."
3. "[solved] Pychromecast not connecting to devices (zeroconf issue) - cast - Home Assistant Community"
   h...

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (1 unchanged, 3 runs per side) | [pytest-pr-1.log:7](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pytest-pr-1.log) «6 passed in 0.77s» |
| P-C1 | The playbackSession fields (appAllowsGrouping, isVideoContent, streamTransferSupported) are parsed from MULTIZONE_STATUS and exposed as MultizoneController.playback_session. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C2 | playback_session is None when no session is attached to the endpoint. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C3 | playback_session is cleared on reset_members(). (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C4 | PLAYBACK_SESSION_UPDATED messages are parsed into a PlaybackSessionUpdate object containing name, changed_devices, failed_devices, and an optional session_endpoint. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C5 | The parsed PlaybackSessionUpdate is delivered to listeners via the new MultiZoneControllerListener.multizone_playback_session_updated callback. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C6 | The multizone_playback_session_updated callback is not abstract, allowing existing listener subclasses to continue working without modification. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| P-C7 | Device IDs in multizone messages are normalized to the dashed form used for members, accommodating devices that report dashless IDs. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |

Citation check (WARN): 1 citation(s) verified; 7 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 1 / 6 | - |
| Tests unchanged | 1 | - |
| New tests that pass | 5 | - |
| Tests that pass on main but fail on the PR | 0 | - |
| Tests that are new in the PR and fail | 0 | - |
| Tests that ran on main but are missing on the PR side | 0 | - |
| Tests that changed result in another way (for example passed -> skipped) | 0 | - |
| Tests that gave different results between the 3 runs of the same side (flaky) | 0 | - |
| Tests that fail on main and pass on the PR | 0 | - |
| Tests that are new or changed but did not run because an optional module is missing | 0 | - |
| Tests that were re-parametrized (same test, new parameter ids; not counted as removed) | 0 | - |
| Test modules that fail to load on the PR side only (their tests no longer run) | 0 | - |
| Test modules that fail to load on main only (no baseline for their tests) | 0 | - |
| Test modules that fail to load on both sides (their tests did not run) | 0 | - |
| Tests that fail identically on both sides (already broken on main) | 0 | - |

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-p1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-p1.py`, frozen `2d7fbf9a54ba` at 2026-10-21T14:05:03.747739+00:00): model-written probe of the changed files (no description given)

- P-C1 (PR description): The playbackSession fields (appAllowsGrouping, isVideoContent, streamTransferSupported) are parsed from MULTIZONE_STATUS and exposed as MultizoneController.playback_session. Expects the covered observations to differ.
- P-C2 (PR description): playback_session is None when no session is attached to the endpoint. Expects the covered observations to differ.
- P-C3 (PR description): playback_session is cleared on reset_members(). Expects the covered observations to differ.
- P-C4 (PR description): PLAYBACK_SESSION_UPDATED messages are parsed into a PlaybackSessionUpdate object containing name, changed_devices, failed_devices, and an optional session_endpoint. Expects the covered observations to differ.
- P-C5 (PR description): The parsed PlaybackSessionUpdate is delivered to listeners via the new MultiZoneControllerListener.multizone_playback_session_updated callback. Expects the covered observations to differ.
- P-C6 (PR description): The multizone_playback_session_updated callback is not abstract, allowing existing listener subclasses to continue working without modification. Expects the covered observations to stay the same.
- P-C7 (PR description): Device IDs in multizone messages are normalized to the dashed form used for members, accommodating devices that report dashless IDs. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 1}` | [probe-model-p1-main-1.jsonl:1](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/probe-model-p1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-p1-pr-1.jsonl:1](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/probe-model-p1-pr-1.jsonl) «"observation": "probe.error"» |

Citation check (PASS): 2 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (1.9 s run).

Coverage gate (python, confidence normal): 41 of 43 changed executable line(s) ran (95%).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `pychromecast/controllers/multizone.py` | 43 | 41 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `e863b6dfeeb6` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: all runs exited 0.
- Changed code was exercised (coverage gate): 41 of 43 changed executable line(s) ran (95%).
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 2 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | could not verify: claim(s) C1, C2, C3, C4 (+2 more) expect a difference but no observation matches (1 test(s) ran on main, 6 on the PR; 5 new test(s) pass, 1 unchanged; probe model-p1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count) | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |
| Every claim cites a real log line | 🟠 **WARN** | 1 citation(s) verified; 7 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | all runs exited 0 |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | 41 of 43 changed executable line(s) ran (95%) |
| Probes ran on both sides | 🟠 **WARN** | model-p1 main#1; model-p1 pr#1; model-p1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 1 citation(s) verified; 7 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 2 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run-folder>/report/pychromecast-1300 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/home-assistant-libs/pychromecast/pull/1300
```

## Evidence links

- [Pull request home-assistant-libs/pychromecast#1300](https://github.com/home-assistant-libs/pychromecast/pull/1300)
- [record.json](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/record.json)
- [pr.diff](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/setup-pr.log)
- [git.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/coverage-pr.json)
- [probe-model-p1-main-1.jsonl](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/probe-model-p1-main-1.jsonl)
- [probe-model-p1-pr-1.jsonl](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/probe-model-p1-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:7](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pytest-main-1.log) «1 passed in 0.76s»
- pr run 1 result: [pytest-pr-1.log:7](../../ops/runs/2026-10-21-check-1931/pychromecast-1300/pytest-pr-1.log) «6 passed in 0.77s»

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
