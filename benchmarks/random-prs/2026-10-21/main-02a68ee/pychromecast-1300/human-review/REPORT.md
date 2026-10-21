# Reviewer report: home-assistant-libs/pychromecast#1300: Expose multizone playback session info

Run `pychromecast-1300`, tested 2026-10-21 19:55 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `02a68eea38919fef2e1b537c3bf5a64bd7c771b5`. Report generated 2026-10-21 20:04 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## 🟠 NEEDS ATTENTION
>
> **Recommended action:** Reject  
> **Confidence:** Medium. The run is trustworthy and found a difference a person should look at. Some checks gave warnings: Probes ran on both sides; Every claim cites a real log line
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Expose multizone playback session info ([home-assistant-libs/pychromecast#1300](https://github.com/home-assistant-libs/pychromecast/pull/1300)).
- **What we observed:** probe: 3 observation(s) need attention: session_update.changed_devices differs and no claim covers it; session_update.count differs and no claim covers it; session_update.name differs and no claim covers it; probe: 1 other observation(s) identical on both sides; probe model-hitl-probe-c1-c8-1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-hitl-probe1-2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; rejected: claim pattern(s) C4, C5, C7 match none of this probe's observation names, so the probe is not counted; probe model-hitl-p1-4 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; tests: 1 test(s) ran on main, 6 on the PR; 5 new test(s) pass, 1 unchanged.
- **What you should do:** Do not approve as is. Read 'What changed in behavior' and decide with the PR author.

The PR "Expose multizone playback session info" is marked "needs_attention" because "session_update.changed_devices differs and no claim covers it", "session_update.count differs and no claim covers it", "session_update.name differs and no claim covers it", and probes such as "probe model-hitl-probe-c1-c8-1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate)", "probe model-hitl-probe1-2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate)", and "probe model-hitl-p1-4 is not_adequate (the probe crashed" are inadequate.

Model summary is advisory; the code verdict above is authoritative.

### Agent swarm (advisory)

| Role | Model | Status | Notes |
|---|---|---|---|
| judge | nvidia/Nemotron-3-Ultra-550b-a55b | ok | 5 labels |
| helper | nvidia/Nemotron-3_5-Lightning | ok | session_update.name: ignore cosmetic renames; session_update.count: noise from dynamic device ordering; session_update.changed_devices: ignore if no functional impact |
| summary | nvidia/nemotron-3-super-120b-a12b | ok | - |

judge/helper/summary are advisory; code owns the verdict

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.9 GB (of 15.6 GB).
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
- Source: Extra dependencies on raspbian Jessie (raspberry pi) · Issue #132 · home-assistant-libs/pychromecast · GitHub — https://github.com/home-assistant-libs/pychromecast/issues/132
- Source: pychromecast/pychromecast/socket_client.py at master · home-assistant-libs/pychromecast · GitHub — https://github.com/home-assistant-libs/pychromecast/blob/master/pychromecast/socket_client.py
- Source: "[WinError 10049] The requested address is not valid in its context" · Issue #483 · home-assistant-libs/pychromecast · GitHub — https://github.com/home-assistant-libs/pychromecast/issues/483
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

## Human review

A person reviewed the AI's probes before anything ran. Probes written from their test ideas are labelled human-requested.

| Item | Value |
|---|---|
| AI probes kept | none |
| AI probes dropped | probe1 |
| Test ideas added | 5 |
| Human-requested probes | hitl-probe-c1-c8-1, hitl-probe1-2, hitl-probe1-3, hitl-p1-4, hitl-probe-unchanged-behavior-5 |
| Claims left with no probe | C9 |

- C1,C8: build MultizoneController(UUID('9a4683f8-a265-4ec7-aab1-a70cb50f4ca7')) and call receive_message(None, {'type':'MULTIZONE_STATUS','requestId':1,'status':{'devices':[],'isMultichannel':False,'playbackSession':{'appAllowsGrouping':True,'isVideoContent':False,'streamTransferSupported':True}}}). Record getattr(controller,'playback_session',<'missing'>) fields app_allows_grouping, is_video_content, stream_transfer_supported as observations 'session_fields.<field>'; on main record the string 'missing'. Do not import constants from pychromecast.const; use the literal message type strings.
- C2,C3: same controller; send a MULTIZONE_STATUS with no playbackSession key and record whether playback_session is None ('session_none.without_session'); then send one with a playbackSession, call reset_members(), and record whether playback_session is None ('session_none.after_reset'). On main record 'missing' when the attribute does not exist.
- C4,C5,C7: register a plain MultiZoneControllerListener subclass that appends each multizone_playback_session_updated argument to a list, then receive_message(None, {'type':'PLAYBACK_SESSION_UPDATED','name':'Group','changedDevices':['be209f090f6a4596ac1a16a77670692b'],'failedDevices':[],'sessionEndpoint':{'deviceId':'be209f090f6a4596ac1a16a77670692b','ipAddress':'192.168.1.5','port':8009,'sessionId':'abc'}}). Record the call count, update.name, update.changed_devices and update.session_endpoint.device_id as 'session_update.*' (count 0 on main). When no update was delivered, record the string 'no_update' for each update field so main and PR values are comparable.
- C6: a listener subclass that only defines multizone_member_added/removed/status_received is registered; send PLAYBACK_SESSION_UPDATED and MULTIZONE_STATUS messages and record 'ok' or the exception type name for each as 'old_listener.update' and 'old_listener.status'. Expect the same on both sides.
- Unchanged behaviour: send MULTIZONE_STATUS with devices Kitchen 'be209f09-0f6a-4596-ac1a-16a77670692b' and Back room '2b514019-b9fa-43b5-a740-b4c3f8882918', record sorted controller.members as 'members_unchanged.before', then send {'type':'DEVICE_REMOVED','deviceId':'be209f09-0f6a-4596-ac1a-16a77670692b'} and record members again as 'members_unchanged.after'. Expect the same on both sides.

A claim with no probe after review cannot be verified, so the verdict is at most could not verify.

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (1 unchanged, 3 runs per side) | [pytest-pr-1.log:7](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pytest-pr-1.log) «6 passed in 0.80s» |
| P-C1 | Only parses messages devices already send; nothing new is sent. (PR description) | ⚪ **not testable** | probe model-hitl-probe-c1-c8-1 has no observation for this claim | no matching log line |
| P-C8 | Normalize device ids to the dashed form used for `members`, since devices also report dashless ids. (PR description) | ⚪ **not testable** | probe model-hitl-probe-c1-c8-1 has no observation for this claim | no matching log line |
| P-C2 | Parse `playbackSession` from `MULTIZONE_STATUS` (`appAllowsGrouping`, `isVideoContent`, `streamTransferSupported`) and expose it as `MultizoneController.playback_session`. (PR description) | ⚪ **not testable** | probe model-hitl-probe1-2 has no observation for this claim | no matching log line |
| P-C3 | The `playback_session` attribute is `None` when no session is attached to the endpoint. (PR description) | ⚪ **not testable** | probe model-hitl-probe1-2 has no observation for this claim | no matching log line |
| P-C4 | The `playback_session` attribute is cleared on `reset_members()`. (PR description) | ⚪ **not testable** | probe model-hitl-probe1-3 has no observation for this claim | no matching log line |
| P-C5 | Parse `PLAYBACK_SESSION_UPDATED` (previously dropped) into a `PlaybackSessionUpdate` (`name`, `changed_devices`, `failed_devices`, optional `session_endpoint`). (PR description) | ⚪ **not testable** | probe model-hitl-probe1-3 has no observation for this claim | no matching log line |
| P-C7 | The `multizone_playback_session_updated` callback is not abstract, so existing listener subclasses keep working. (PR description) | ⚪ **not testable** | probe model-hitl-probe1-3 has no observation for this claim | no matching log line |
| - | Change not in the PR description (probe model-hitl-probe1-3) | 🟠 **unmentioned change** | session_update.changed_devices: `value`: "no_update" -> ["<uuid>"] | [probe-model-hitl-probe1-3-pr-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-pr-1.jsonl) «"observation": "session_update.changed_devices"» |
| - | Change not in the PR description (probe model-hitl-probe1-3) | 🟠 **unmentioned change** | session_update.count: `value`: 0 -> 1 | [probe-model-hitl-probe1-3-pr-1.jsonl:2](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-pr-1.jsonl) «"observation": "session_update.count"» |
| - | Change not in the PR description (probe model-hitl-probe1-3) | 🟠 **unmentioned change** | session_update.name: `value`: "no_update" -> "Group" | [probe-model-hitl-probe1-3-pr-1.jsonl:3](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-pr-1.jsonl) «"observation": "session_update.name"» |
| P-C6 | Pass the `PlaybackSessionUpdate` to listeners via a new `MultiZoneControllerListener.multizone_playback_session_updated` callback. (PR description) | ⚪ **not testable** | probe model-hitl-p1-4 has no observation for this claim | no matching log line |
| P-C7 | The `multizone_playback_session_updated` callback is not abstract, so existing listener subclasses keep working. (PR description) | ⚪ **not testable** | probe model-hitl-p1-4 has no observation for this claim | no matching log line |

Citation check (WARN): 4 citation(s) verified; 9 statement(s) have no matching log line.

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

**model-hitl-probe-c1-c8-1** (human-requested, model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-hitl-probe-c1-c8-1.py`, frozen `dcad1afac4fb` at 2026-10-21T14:33:30.414638+00:00): MultizoneController receives MULTIZONE_STATUS with playbackSession and exposes playback_session attribute

- P-C1 (PR description): Only parses messages devices already send; nothing new is sent. Expects the covered observations to stay the same.
- P-C8 (PR description): Normalize device ids to the dashed form used for `members`, since devices also report dashless ids. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 0}` | [probe-model-hitl-probe-c1-c8-1-main-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe-c1-c8-1-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-hitl-probe-c1-c8-1-pr-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe-c1-c8-1-pr-1.jsonl) «"observation": "probe.error"» |

**model-hitl-probe1-2** (human-requested, model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-hitl-probe1-2.py`, frozen `acd69e04bebf` at 2026-10-21T14:33:30.415029+00:00): MultizoneController.playback_session attribute existence and value after MULTIZONE_STATUS messages and reset_members()

- P-C2 (PR description): Parse `playbackSession` from `MULTIZONE_STATUS` (`appAllowsGrouping`, `isVideoContent`, `streamTransferSupported`) and expose it as `MultizoneController.playback_session`. Expects the covered observations to differ.
- P-C3 (PR description): The `playback_session` attribute is `None` when no session is attached to the endpoint. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 0}` | [probe-model-hitl-probe1-2-main-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-2-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-hitl-probe1-2-pr-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-2-pr-1.jsonl) «"observation": "probe.error"» |

**model-hitl-probe1-3** (human-requested, model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-hitl-probe1-3.py`, frozen `da6b187187ca` at 2026-10-21T14:33:30.415515+00:00): Tests that PLAYBACK_SESSION_UPDATED messages do not trigger the multizone_playback_session_updated listener in the base code.

- P-C4 (PR description): The `playback_session` attribute is cleared on `reset_members()`. Expects the covered observations to differ.
- P-C5 (PR description): Parse `PLAYBACK_SESSION_UPDATED` (previously dropped) into a `PlaybackSessionUpdate` (`name`, `changed_devices`, `failed_devices`, optional `session_endpoint`). Expects the covered observations to differ.
- P-C7 (PR description): The `multizone_playback_session_updated` callback is not abstract, so existing listener subclasses keep working. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `session_update.changed_devices` | - | 🟠 **differs, not in the PR description** | `value`: "no_update" -> ["<uuid>"] | [probe-model-hitl-probe1-3-main-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-main-1.jsonl) «"observation": "session_update.changed_devices"»<br>[probe-model-hitl-probe1-3-pr-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-pr-1.jsonl) «"observation": "session_update.changed_devices"» |
| `session_update.count` | - | 🟠 **differs, not in the PR description** | `value`: 0 -> 1 | [probe-model-hitl-probe1-3-main-1.jsonl:2](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-main-1.jsonl) «"observation": "session_update.count"»<br>[probe-model-hitl-probe1-3-pr-1.jsonl:2](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-pr-1.jsonl) «"observation": "session_update.count"» |
| `session_update.name` | - | 🟠 **differs, not in the PR description** | `value`: "no_update" -> "Group" | [probe-model-hitl-probe1-3-main-1.jsonl:3](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-main-1.jsonl) «"observation": "session_update.name"»<br>[probe-model-hitl-probe1-3-pr-1.jsonl:3](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-pr-1.jsonl) «"observation": "session_update.name"» |
| `session_update.session_endpoint_device_id` | - | 🟢 **same on both sides** | same on both sides: `"no_update"` | [probe-model-hitl-probe1-3-main-1.jsonl:4](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-main-1.jsonl) «"observation": "session_update.session_endpoint_device_id"»<br>[probe-model-hitl-probe1-3-pr-1.jsonl:4](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-pr-1.jsonl) «"observation": "session_update.session_endpoint_device_id"» |

**model-hitl-p1-4** (human-requested, model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-hitl-p1-4.py`, frozen `862e52275fff` at 2026-10-21T14:33:30.415831+00:00): Check that legacy listener handles PLAYBACK_SESSION_UPDATED and MULTIZONE_STATUS without breaking

- P-C6 (PR description): Pass the `PlaybackSessionUpdate` to listeners via a new `MultiZoneControllerListener.multizone_playback_session_updated` callback. Expects the covered observations to differ.
- P-C7 (PR description): The `multizone_playback_session_updated` callback is not abstract, so existing listener subclasses keep working. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe.error` | - | ⚪ **probe could not run** | same on both sides: `{"crash": "non-json output", "exit_code": 0}` | [probe-model-hitl-p1-4-main-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-p1-4-main-1.jsonl) «"observation": "probe.error"»<br>[probe-model-hitl-p1-4-pr-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-p1-4-pr-1.jsonl) «"observation": "probe.error"» |

**model-hitl-probe-unchanged-behavior-5** (human-requested, model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-hitl-probe-unchanged-behavior-5.py`, frozen `12f75a64218c` at 2026-10-21T14:33:30.416093+00:00): pychromecast/controllers/multizone.py

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `error` | - | 🟢 **same on both sides** | same on both sides: `"KeyError"` | [probe-model-hitl-probe-unchanged-behavior-5-main-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe-unchanged-behavior-5-main-1.jsonl) «"observation": "error"»<br>[probe-model-hitl-probe-unchanged-behavior-5-pr-1.jsonl:1](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe-unchanged-behavior-5-pr-1.jsonl) «"observation": "error"» |

Citation check (PASS): 16 citation(s), every one re-read from its log file and matched.

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
- Every probe observation cites its output line: 16 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Probes ran on both sides | 🟠 **WARN** | model-hitl-probe-c1-c8-1 main#1; model-hitl-probe-c1-c8-1 pr#1; model-hitl-probe-c1-c8-1 main#2 | Read the probe-*.log files; a probe that cannot run is not evidence either way. |
| Every claim cites a real log line | 🟠 **WARN** | 4 citation(s) verified; 9 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |
| Behavior difference found | 🟠 **finding** | probe: 3 observation(s) need attention: session_update.changed_devices differs and no claim covers it; session_update.count differs and no claim covers it; session_update.name differs and no claim covers it; probe: 1 other observation(s) identical on both sides; probe model-hitl-probe-c1-c8-1 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; probe model-hitl-probe1-2 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; rejected: claim pattern(s) C4, C5, C7 match none of this probe's observation names, so the probe is not counted; probe model-hitl-p1-4 is not_adequate (the probe crashed or printed no parsed output on every main-side run; not counted as ran or adequate); its matching results do not count; tests: 1 test(s) ran on main, 6 on the PR; 5 new test(s) pass, 1 unchanged | This is about the PR, not the run: read the failing tests and their log lines, then decide. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | all runs exited 0 |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | 41 of 43 changed executable line(s) ran (95%) |
| Probes ran on both sides | 🟠 **WARN** | model-hitl-probe-c1-c8-1 main#1; model-hitl-probe-c1-c8-1 pr#1; model-hitl-probe-c1-c8-1 main#2 |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 4 citation(s) verified; 9 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 16 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=./report/pychromecast-1300 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/home-assistant-libs/pychromecast/pull/1300
```

## Evidence links

- [Pull request home-assistant-libs/pychromecast#1300](https://github.com/home-assistant-libs/pychromecast/pull/1300)
- [record.json](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/record.json)
- [pr.diff](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/setup-pr.log)
- [git.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/coverage-pr.json)
- [probe-model-hitl-probe-c1-c8-1-main-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe-c1-c8-1-main-1.jsonl)
- [probe-model-hitl-probe-c1-c8-1-pr-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe-c1-c8-1-pr-1.jsonl)
- [probe-model-hitl-probe1-2-main-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-2-main-1.jsonl)
- [probe-model-hitl-probe1-2-pr-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-2-pr-1.jsonl)
- [probe-model-hitl-probe1-3-main-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-main-1.jsonl)
- [probe-model-hitl-probe1-3-pr-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe1-3-pr-1.jsonl)
- [probe-model-hitl-p1-4-main-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-p1-4-main-1.jsonl)
- [probe-model-hitl-p1-4-pr-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-p1-4-pr-1.jsonl)
- [probe-model-hitl-probe-unchanged-behavior-5-main-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe-unchanged-behavior-5-main-1.jsonl)
- [probe-model-hitl-probe-unchanged-behavior-5-pr-1.jsonl](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/probe-model-hitl-probe-unchanged-behavior-5-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:7](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pytest-main-1.log) «1 passed in 0.77s»
- pr run 1 result: [pytest-pr-1.log:7](../../ops/runs/2026-10-21-check-1955/pychromecast-1300/pytest-pr-1.log) «6 passed in 0.80s»

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
