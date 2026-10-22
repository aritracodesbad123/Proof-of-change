# Reviewer report: Second-Hand-Friends/kleinanzeigen-bot#1361: feat: add manual browser login command

Run `kleinanzeigen_bot-1361`, tested 2026-10-22 01:15 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 01:18 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## 🟠 NEEDS ATTENTION
>
> **Recommended action:** Reject  
> **Confidence:** Medium. The run is trustworthy and found a difference a person should look at. Some checks gave warnings: Every claim cites a real log line
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** feat: add manual browser login command ([Second-Hand-Friends/kleinanzeigen-bot#1361](https://github.com/Second-Hand-Friends/kleinanzeigen-bot/pull/1361)).
- **What we observed:** 1 new test(s) fail on the PR; 322 test(s) ran on main, 335 on the PR; 12 new test(s) pass, 307 unchanged; 15 test failure(s) pre-existing and identical on both sides; probe: 1 observation(s) need attention: probe1.exit_code differs and no claim covers it; rejected: claim pattern(s) C1, C4 match none of this probe's observation names, so the probe is not counted; rejected: claim pattern(s) C2, C3, C4, C5 match none of this probe's observation names, so the probe is not counted.
- **What you should do:** Do not approve as is. Read 'What changed in behavior' and decide with the PR author.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.6 GB (of 15.6 GB).
- Setup check: free disk 93.1 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 0 results
- Query: kleinanzeigen-bot python setup install instructions https://github.com/Second-Hand-Friends/kleinanzeigen-bot site:github.com/Second-Hand-Friends/kleinanzeigen-bot
- Query: kleinanzeigen-bot python documentation install https://github.com/Second-Hand-Friends/kleinanzeigen-bot site:github.com/Second-Hand-Friends/kleinanzeigen-bot
- Query: kleinanzeigen-bot python install requirements https://pypi.org/project/kleinanzeigen-bot/ https://github.com/Second-Hand-Friends/kleinanzeigen-bot site:pypi.org
- Setup plan: the same packages on main and pr.
- Setup plan: certifi is noted, installed with the project.
- Setup plan: colorama is noted, installed with the project.
- Setup plan: jaraco.text is noted, installed with the project.
- Setup plan: nodriver is noted, installed with the project.
- Setup plan: platformdirs is noted, installed with the project.
- Setup plan: pydantic is noted, installed with the project.
- Setup plan: ruamel.yaml is noted, installed with the project.
- Setup plan: psutil is noted, installed with the project.
- Setup plan: wcmatch is noted, installed with the project.
- Setup plan: sanitize-filename is noted, installed with the project.
- Setup plan: requests is noted, installed with the project.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.12,<3.16

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🔴 **false** | 1 test(s) fail on the PR, e.g. tests.integration.test_web_scraping_mixin_integration::test_closing_a_session_persists_cookies_for_the_next_start | [pytest-pr-1.log:1611](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-pr-1.log) «FAILED tests/integration/test_web_scraping_mixin_integration.py::test_closing_a_session_persists_cookies_for_the_next_start» |
| P-C1 | Add `login`, which opens the configured browser profile visibly, lets the user authenticate, then verifies the configured account after ENTER and closes the managed browser. (PR description) | ⚪ **not testable** | probe model-probe1 has no observation for this claim | no matching log line |
| P-C4 | Reject noninteractive input, verify the configured account, and close browser resources on success/failure. (PR description) | ⚪ **not testable** | probe model-probe1 has no observation for this claim | no matching log line |
| - | Change not in the PR description (probe model-probe1) | 🟠 **unmentioned change** | probe1.exit_code: `value`: 2 -> 1 | [probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe1-pr-1.jsonl) «"observation": "probe1.exit_code"» |
| P-C2 | In Docker it works with the browser desktop of the standard image (#1357). (PR description) | ⚪ **not testable** | probe model-probe2 has no observation for this claim | no matching log line |
| P-C3 | Force a persistent visible session for this command only (no private/guest/headless arguments), without changing config files or submitting credentials/SMS requests. (PR description) | ⚪ **not testable** | probe model-probe2 has no observation for this claim | no matching log line |
| P-C4 | Reject noninteractive input, verify the configured account, and close browser resources on success/failure. (PR description) | ⚪ **not testable** | probe model-probe2 has no observation for this claim | no matching log line |
| P-C5 | Warn when private/guest mode in the normal config would prevent later session reuse. (PR description) | ⚪ **not testable** | probe model-probe2 has no observation for this claim | no matching log line |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 1 test(s) are new in the PR and fail, e.g. tests.integration.test_web_scraping_mixin_integration::test_closing_a_session_persists_cookies_for_the_next_start | [pytest-pr-1.log:1611](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-pr-1.log) «FAILED tests/integration/test_web_scraping_mixin_integration.py::test_closing_a_session_persists_cookies_for_the_next_start» |

Citation check (WARN): 3 citation(s) verified; 6 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 322 / 335 | - |
| Tests unchanged | 322 | - |
| New tests that pass | 12 | - |
| Tests that pass on main but fail on the PR | 0 | - |
| Tests that are new in the PR and fail | 1 | `tests.integration.test_web_scraping_mixin_integration::test_closing_a_session_persists_cookies_for_the_next_start` |
| Tests that ran on main but are missing on the PR side | 0 | - |
| Tests that changed result in another way (for example passed -> skipped) | 0 | - |
| Tests that gave different results between the 3 runs of the same side (flaky) | 0 | - |
| Tests that fail on main and pass on the PR | 0 | - |
| Tests that are new or changed but did not run because an optional module is missing | 0 | - |
| Tests that were re-parametrized (same test, new parameter ids; not counted as removed) | 0 | - |
| Test modules that fail to load on the PR side only (their tests no longer run) | 0 | - |
| Test modules that fail to load on main only (no baseline for their tests) | 0 | - |
| Test modules that fail to load on both sides (their tests did not run) | 0 | - |
| Tests that fail identically on both sides (already broken on main) | 15 | `tests.integration.test_web_scraping_mixin_integration::test_init`, `tests.integration.test_web_scraping_mixin_integration::test_logged_in_marker_is_detected_on_redesigned_start_page_at_any_viewport_width[1024-True]`, `tests.integration.test_web_scraping_mixin_integration::test_logged_in_marker_is_detected_on_redesigned_start_page_at_any_viewport_width[390-False]`, `tests.integration.test_web_scraping_mixin_integration::test_sms_verification_prompts_at_request_and_entry_stages[<p>Ger\xe4t best\xe4tigen<br>Wir senden dir einen Code.</p><button>Code senden</button>-True]`, `tests.integration.test_web_scraping_mixin_integration::test_sms_verification_prompts_at_request_and_entry_stages[<p>Willkommen</p>-False]` |

`tests.integration.test_web_scraping_mixin_integration::test_closing_a_session_persists_cookies_for_the_next_start` fails with: `AssertionError: Installed browser could not be detected`

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-probe1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe1.py`, frozen `82b30287eedd` at 2026-10-21T19:47:31.180236+00:00): Test login command recognition and non-interactive rejection

- P-C1 (PR description): Add `login`, which opens the configured browser profile visibly, lets the user authenticate, then verifies the configured account after ENTER and closes the managed browser. Expects the covered observations to differ.
- P-C4 (PR description): Reject noninteractive input, verify the configured account, and close browser resources on success/failure. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe1.exit_code` | - | 🟠 **differs, not in the PR description** | `value`: 2 -> 1 | [probe-model-probe1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe1-main-1.jsonl) «"observation": "probe1.exit_code"»<br>[probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe1-pr-1.jsonl) «"observation": "probe1.exit_code"» |
| `probe1.stderr` | - | 🟢 **same on both sides** | same on both sides: `"\u001b[33m[WARNING]\u001b[0m \u001b[33mnodriver CDP re-attach patch not found: install...` | [probe-model-probe1-main-1.jsonl:2](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe1-main-1.jsonl) «"observation": "probe1.stderr"»<br>[probe-model-probe1-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe1-pr-1.jsonl) «"observation": "probe1.stderr"» |
| `probe1.stdout` | - | 🟢 **same on both sides** | same on both sides: `" _    _      _                           _                       _           _\n\| \| _\|...` | [probe-model-probe1-main-1.jsonl:3](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe1-main-1.jsonl) «"observation": "probe1.stdout"»<br>[probe-model-probe1-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe1-pr-1.jsonl) «"observation": "probe1.stdout"» |

**model-probe2** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe2.py`, frozen `92d626db0e98` at 2026-10-21T19:47:31.180399+00:00): Test config file unchanged and private mode warning

- P-C2 (PR description): In Docker it works with the browser desktop of the standard image (#1357). Expects the covered observations to differ.
- P-C3 (PR description): Force a persistent visible session for this command only (no private/guest/headless arguments), without changing config files or submitting credentials/SMS requests. Expects the covered observations to differ.
- P-C4 (PR description): Reject noninteractive input, verify the configured account, and close browser resources on success/failure. Expects the covered observations to differ.
- P-C5 (PR description): Warn when private/guest mode in the normal config would prevent later session reuse. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `probe2.config_unchanged` | - | 🟢 **same on both sides** | same on both sides: `true` | [probe-model-probe2-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe2-main-1.jsonl) «"observation": "probe2.config_unchanged"»<br>[probe-model-probe2-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe2-pr-1.jsonl) «"observation": "probe2.config_unchanged"» |
| `probe2.warning_found` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-model-probe2-main-1.jsonl:2](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe2-main-1.jsonl) «"observation": "probe2.warning_found"»<br>[probe-model-probe2-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe2-pr-1.jsonl) «"observation": "probe2.warning_found"» |

**diff-api** (diff (auto-derived from base-side code, model-free); informational under baseline full, `diff-probes/diff-api.py`, frozen `763b4ca5a87d` at 2026-10-21T19:47:31.201394+00:00): Public functions touched by the PR, called with type-appropriate inputs on both sides.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `kleinanzeigen_bot.cli.help_text.input0` | - | 🟢 **same on both sides** | same on both sides: `"Usage: \u001b[95mpython -m kleinanzeigen_bot COMMAND [OPTIONS]\u001b[0m\n\nCommands:\n...` | [probe-diff-api-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-diff-api-main-1.jsonl) «"observation": "kleinanzeigen_bot.cli.help_text.input0"»<br>[probe-diff-api-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-diff-api-pr-1.jsonl) «"observation": "kleinanzeigen_bot.cli.help_text.input0"» |

Citation check (PASS): 12 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (10.1 s run).

Coverage gate (python, confidence normal): 27 of 27 changed executable line(s) ran (100%).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `src/kleinanzeigen_bot/app.py` | 18 | 18 |
| `src/kleinanzeigen_bot/cli.py` | 0 | 0 |
| `src/kleinanzeigen_bot/runtime_config.py` | 0 | 0 |
| `src/kleinanzeigen_bot/utils/web_scraping_mixin.py` | 9 | 9 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `5258d75baff4` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: pytest exit 1; 15 failure(s)/error(s) pre-existing and identical on both sides.
- Changed code was exercised (coverage gate): 27 of 27 changed executable line(s) ran (100%).
- Probes ran on both sides: 3 probe(s), 3 alternating runs per side, every run printed its observations.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 12 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Every claim cites a real log line | 🟠 **WARN** | 3 citation(s) verified; 6 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |
| Behavior difference found | 🟠 **finding** | 1 new test(s) fail on the PR; 322 test(s) ran on main, 335 on the PR; 12 new test(s) pass, 307 unchanged; 15 test failure(s) pre-existing and identical on both sides; probe: 1 observation(s) need attention: probe1.exit_code differs and no claim covers it; rejected: claim pattern(s) C1, C4 match none of this probe's observation names, so the probe is not counted; rejected: claim pattern(s) C2, C3, C4, C5 match none of this probe's observation names, so the probe is not counted | This is about the PR, not the run: read the failing tests and their log lines, then decide. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | pytest exit 1; 15 failure(s)/error(s) pre-existing and identical on both sides |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | 27 of 27 changed executable line(s) ran (100%) |
| Probes ran on both sides | 🟢 **PASS** | 3 probe(s), 3 alternating runs per side, every run printed its observations |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 3 citation(s) verified; 6 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 12 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/kleinanzeigen_bot-1361 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/Second-Hand-Friends/kleinanzeigen-bot/pull/1361
```

## Evidence links

- [Pull request Second-Hand-Friends/kleinanzeigen-bot#1361](https://github.com/Second-Hand-Friends/kleinanzeigen-bot/pull/1361)
- [record.json](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/coverage-pr.json)
- [probe-model-probe1-main-1.jsonl](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe1-main-1.jsonl)
- [probe-model-probe1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe1-pr-1.jsonl)
- [probe-model-probe2-main-1.jsonl](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe2-main-1.jsonl)
- [probe-model-probe2-pr-1.jsonl](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-model-probe2-pr-1.jsonl)
- [probe-diff-api-main-1.jsonl](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-diff-api-main-1.jsonl)
- [probe-diff-api-pr-1.jsonl](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/probe-diff-api-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:1540](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-main-1.log) «3 failed, 307 passed, 5 warnings, 12 errors in 5.67s»
- pr run 1 result: [pytest-pr-1.log:1627](../../ops/runs/2026-10-22-check-0115/kleinanzeigen_bot-1361/pytest-pr-1.log) «4 failed, 319 passed, 5 warnings, 12 errors in 5.76s»

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
