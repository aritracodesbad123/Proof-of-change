# Reviewer report: caronc/apprise#1783: tags= and tag= on urls not supported

Run `apprise-1783`, tested 2026-10-22 01:52 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 01:53 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## 🟠 NEEDS ATTENTION
>
> **Recommended action:** Reject  
> **Confidence:** Medium. The run is trustworthy and found a difference a person should look at. Some checks gave warnings: Every claim cites a real log line
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** tags= and tag= on urls not supported ([caronc/apprise#1783](https://github.com/caronc/apprise/pull/1783)).
- **What we observed:** 10 test(s) removed on the PR side; 274 test(s) ran on main, 274 on the PR; 10 new test(s) pass, 264 unchanged; rejected: claim pattern(s) C1 match none of this probe's observation names, so the probe is not counted.
- **What you should do:** Do not approve as is. Read 'What changed in behavior' and decide with the PR author.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 5.8 GB (of 15.6 GB).
- Setup check: free disk 92.7 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 8 results
- Query: apprise python setup install instructions https://github.com/caronc/apprise site:github.com/caronc/apprise
- Query: apprise python documentation install https://github.com/caronc/apprise site:github.com/caronc/apprise
- Query: apprise python install requirements https://pypi.org/project/apprise/ https://github.com/caronc/apprise site:pypi.org
- Source: mka142-apprise · PyPI — https://pypi.org/project/mka142-apprise/
- Source: apprise · PyPI — https://pypi.org/project/apprise/
- Source: Matrix notifications could be end-to-end encrypted · Issue #305 · caronc/apprise · GitHub — https://github.com/caronc/apprise/issues/305
- Source: GitHub - caronc/apprise: Apprise - Push Notifications that work with just about every platform! · GitHub — https://github.com/caronc/apprise
- Source: apprise/CONTRIBUTING.md at master · caronc/apprise · GitHub — https://github.com/caronc/apprise/blob/master/CONTRIBUTING.md
- Source: Releases · caronc/apprise · GitHub — https://github.com/caronc/apprise/releases
- Source: GitHub - caronc/apprise-docs: Apprise Documentation · GitHub — https://github.com/caronc/apprise-docs
- Source: PyPI · The Python Package Index — https://pypi.org
- Setup plan: the same packages on main and pr.
- Setup plan: requests is noted, installed with the project.
- Setup plan: urllib3 is noted, installed with the project.
- Setup plan: requests-oauthlib is noted, installed with the project.
- Setup plan: click is noted, installed with the project.
- Setup plan: markdown is noted, installed with the project.
- Setup plan: PyYAML is noted, installed with the project.
- Setup plan: certifi is noted, installed with the project.
- Setup plan: tzdata is noted, installed with the project.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.9

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (264 unchanged, 3 runs per side) | [pytest-pr-1.log:19](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-pr-1.log) «274 passed, 4 warnings in 2.79s» |
| P-C1 | The query parameters ?tag= and ?tags= are handled exactly like ?asset=. (PR description) | ⚪ **not testable** | probe model-p1 has no observation for this claim | no matching log line |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 10 test(s) ran on main but are missing on the PR side, e.g. tests.test_apprise_template::test_apprise_template_rejects_tag_variable[json://localhost/?+tag=${T}] | [pytest-main-1.log:19](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-main-1.log) «274 passed, 4 warnings in 2.83s» |

Citation check (WARN): 2 citation(s) verified; 1 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 274 / 274 | - |
| Tests unchanged | 264 | - |
| New tests that pass | 10 | - |
| Tests that pass on main but fail on the PR | 0 | - |
| Tests that are new in the PR and fail | 0 | - |
| Tests that ran on main but are missing on the PR side | 10 | `tests.test_apprise_template::test_apprise_template_rejects_tag_variable[json://localhost/?+tag=${T}]`, `tests.test_apprise_template::test_apprise_template_rejects_tag_variable[json://localhost/?-tag=${T}]`, `tests.test_apprise_template::test_apprise_template_rejects_tag_variable[json://localhost/?:tag=${T}]`, `tests.test_apprise_template::test_apprise_template_rejects_tag_variable[json://localhost/?tag=${T}]`, `tests.test_apprise_template::test_apprise_template_rejects_tag_variable[json://localhost/?tags=${T}]` |
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

**model-p1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-p1.py`, frozen `2d652cbfd0de` at 2026-10-21T20:22:57.818147+00:00): Check the YAML_REAPPLY_SKIP set for tag, tags, and asset

- P-C1 (PR description): The query parameters ?tag= and ?tags= are handled exactly like ?asset=. Expects the covered observations to stay the same.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `yaml_reapply_skip_contents` | - | 🟢 **same on both sides** | same on both sides: `["asset", "tag", "tags"]` | [probe-model-p1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-main-1.jsonl) «"observation": "yaml_reapply_skip_contents"»<br>[probe-model-p1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-pr-1.jsonl) «"observation": "yaml_reapply_skip_contents"» |
| `yaml_reapply_skip_has_asset` | - | 🟢 **same on both sides** | same on both sides: `true` | [probe-model-p1-main-1.jsonl:2](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-main-1.jsonl) «"observation": "yaml_reapply_skip_has_asset"»<br>[probe-model-p1-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-pr-1.jsonl) «"observation": "yaml_reapply_skip_has_asset"» |
| `yaml_reapply_skip_has_tag` | - | 🟢 **same on both sides** | same on both sides: `true` | [probe-model-p1-main-1.jsonl:3](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-main-1.jsonl) «"observation": "yaml_reapply_skip_has_tag"»<br>[probe-model-p1-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-pr-1.jsonl) «"observation": "yaml_reapply_skip_has_tag"» |
| `yaml_reapply_skip_has_tags` | - | 🟢 **same on both sides** | same on both sides: `true` | [probe-model-p1-main-1.jsonl:4](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-main-1.jsonl) «"observation": "yaml_reapply_skip_has_tags"»<br>[probe-model-p1-pr-1.jsonl:4](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-pr-1.jsonl) «"observation": "yaml_reapply_skip_has_tags"» |
| `yaml_reapply_skip_import_exception` | - | 🟢 **same on both sides** | same on both sides: `null` | [probe-model-p1-main-1.jsonl:5](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-main-1.jsonl) «"observation": "yaml_reapply_skip_import_exception"»<br>[probe-model-p1-pr-1.jsonl:5](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-pr-1.jsonl) «"observation": "yaml_reapply_skip_import_exception"» |
| `yaml_reapply_skip_length` | - | 🟢 **same on both sides** | same on both sides: `3` | [probe-model-p1-main-1.jsonl:6](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-main-1.jsonl) «"observation": "yaml_reapply_skip_length"»<br>[probe-model-p1-pr-1.jsonl:6](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-pr-1.jsonl) «"observation": "yaml_reapply_skip_length"» |
| `yaml_reapply_skip_type` | - | 🟢 **same on both sides** | same on both sides: `"<class 'frozenset'>"` | [probe-model-p1-main-1.jsonl:7](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-main-1.jsonl) «"observation": "yaml_reapply_skip_type"»<br>[probe-model-p1-pr-1.jsonl:7](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-pr-1.jsonl) «"observation": "yaml_reapply_skip_type"» |

**diff-api** (diff (auto-derived from base-side code, model-free); informational under baseline full, `diff-probes/diff-api.py`, frozen `a2444305993d` at 2026-10-21T20:22:57.819529+00:00): Public functions touched by the PR, called with type-appropriate inputs on both sides.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `apprise.utils.yaml.templated_tag.input0` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input0"»<br>[probe-diff-api-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input0"» |
| `apprise.utils.yaml.templated_tag.input1` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:2](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input1"»<br>[probe-diff-api-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input1"» |
| `apprise.utils.yaml.templated_tag.input10` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:3](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input10"»<br>[probe-diff-api-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input10"» |
| `apprise.utils.yaml.templated_tag.input11` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:4](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input11"»<br>[probe-diff-api-pr-1.jsonl:4](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input11"» |
| `apprise.utils.yaml.templated_tag.input2` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:5](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input2"»<br>[probe-diff-api-pr-1.jsonl:5](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input2"» |
| `apprise.utils.yaml.templated_tag.input3` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:6](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input3"»<br>[probe-diff-api-pr-1.jsonl:6](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input3"» |
| `apprise.utils.yaml.templated_tag.input4` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:7](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input4"»<br>[probe-diff-api-pr-1.jsonl:7](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input4"» |
| `apprise.utils.yaml.templated_tag.input5` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:8](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input5"»<br>[probe-diff-api-pr-1.jsonl:8](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input5"» |
| `apprise.utils.yaml.templated_tag.input6` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:9](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input6"»<br>[probe-diff-api-pr-1.jsonl:9](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input6"» |
| `apprise.utils.yaml.templated_tag.input7` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:10](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input7"»<br>[probe-diff-api-pr-1.jsonl:10](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input7"» |
| `apprise.utils.yaml.templated_tag.input8` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:11](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input8"»<br>[probe-diff-api-pr-1.jsonl:11](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input8"» |
| `apprise.utils.yaml.templated_tag.input9` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-diff-api-main-1.jsonl:12](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input9"»<br>[probe-diff-api-pr-1.jsonl:12](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl) «"observation": "apprise.utils.yaml.templated_tag.input9"» |

Citation check (PASS): 38 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (5.4 s run).

Coverage gate (python, confidence normal): the changed Python lines are not executable (comments, docstrings, blank lines).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `apprise/utils/yaml.py` | 0 | 0 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `133d8b877e87` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: all runs exited 0.
- Changed code was exercised (coverage gate): the changed Python lines are not executable (comments, docstrings, blank lines).
- Probes ran on both sides: 2 probe(s), 3 alternating runs per side, every run printed its observations.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 38 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Every claim cites a real log line | 🟠 **WARN** | 2 citation(s) verified; 1 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |
| Behavior difference found | 🟠 **finding** | 10 test(s) removed on the PR side; 274 test(s) ran on main, 274 on the PR; 10 new test(s) pass, 264 unchanged; rejected: claim pattern(s) C1 match none of this probe's observation names, so the probe is not counted | This is about the PR, not the run: read the failing tests and their log lines, then decide. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | all runs exited 0 |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | the changed Python lines are not executable (comments, docstrings, blank lines) |
| Probes ran on both sides | 🟢 **PASS** | 2 probe(s), 3 alternating runs per side, every run printed its observations |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟠 **WARN** | 2 citation(s) verified; 1 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 38 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/apprise-1783 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/caronc/apprise/pull/1783
```

## Evidence links

- [Pull request caronc/apprise#1783](https://github.com/caronc/apprise/pull/1783)
- [record.json](../../ops/runs/2026-10-22-check-0152/apprise-1783/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0152/apprise-1783/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0152/apprise-1783/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0152/apprise-1783/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0152/apprise-1783/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-0152/apprise-1783/coverage-pr.json)
- [probe-model-p1-main-1.jsonl](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-main-1.jsonl)
- [probe-model-p1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-model-p1-pr-1.jsonl)
- [probe-diff-api-main-1.jsonl](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-main-1.jsonl)
- [probe-diff-api-pr-1.jsonl](../../ops/runs/2026-10-22-check-0152/apprise-1783/probe-diff-api-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:19](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-main-1.log) «274 passed, 4 warnings in 2.83s»
- pr run 1 result: [pytest-pr-1.log:19](../../ops/runs/2026-10-22-check-0152/apprise-1783/pytest-pr-1.log) «274 passed, 4 warnings in 2.79s»

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
