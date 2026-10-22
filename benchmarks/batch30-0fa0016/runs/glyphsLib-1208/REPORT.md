# Reviewer report: googlefonts/glyphsLib#1208: split comma-separated meta Table dlng/slng data

Run `glyphslib-1208`, tested 2026-10-22 07:48 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 07:51 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## ⚪ COULD NOT VERIFY
>
> **Recommended action:** Re-run  
> **Confidence:** Low. The run did not produce a usable comparison, so there is no conclusion about the PR. The run did not finish cleanly, so it says nothing about the PR.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** split comma-separated meta Table dlng/slng data ([googlefonts/glyphsLib#1208](https://github.com/googlefonts/glyphsLib/pull/1208)).
- **What we observed:** could not verify: claim(s) C1 expect a difference but no observation matches (docstring-only change (AST equal after blanking docstrings); behaviour claims hold by construction).
- **What you should do:** Do not decide yet. Fix the problem under 'How to fix' and run the check again.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 6.9 GB (of 15.6 GB).
- Setup check: free disk 92.0 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 3 results
- Query: glyphsLib python setup install instructions https://github.com/googlefonts/glyphsLib site:github.com/googlefonts/glyphsLib
- Query: glyphsLib python documentation install https://github.com/googlefonts/glyphsLib site:github.com/googlefonts/glyphsLib
- Query: glyphsLib python install requirements https://pypi.org/project/glyphsLib/ https://github.com/googlefonts/glyphsLib site:pypi.org
- Source: glyphsLib — https://pypi.org/project/glyphsLib/
- Source: GitHub - googlefonts/glyphsLib: A bridge from Glyphs source files (.glyphs) to UFOs · GitHub — https://github.com/googlefonts/glyphsLib
- Source: Handle smart components · Issue #91 · googlefonts/glyphsLib · GitHub — https://github.com/googlefonts/glyphsLib/issues/91
- Setup plan: the same packages on main and pr.
- Setup plan: ufoLib2 is noted, installed with the project.
- Setup plan: fonttools is noted, installed with the project.
- Setup plan: openstep-plist is noted, installed with the project.
- Setup plan: install attrs==26.1.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install black==26.5.1 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install booleanoperations==0.10.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install cffsubr==0.4.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install click==8.4.2 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install coverage==7.15.2 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install defcon==0.12.2 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install execnet==2.1.2 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install flake8==7.3.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install flake8-bugbear==25.11.29 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install fontmath==0.10.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install iniconfig==2.3.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install lxml==6.1.1 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install mccabe==0.7.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install mypy-extensions==1.1.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install packaging==26.2 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pathspec==1.1.1 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install platformdirs==4.11.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pluggy==1.6.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pyclipper==1.4.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pycodestyle==2.14.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pyflakes==3.4.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pygments==2.20.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pytest==9.1.1 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pytest-randomly==4.1.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pytest-xdist==3.8.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install pytokens==0.4.1 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install skia-pathops==0.9.2 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install ufo2ft==3.9.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install ufonormalizer==0.6.3 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install unicodedata2==17.0.1 (listed in requirements-dev.txt) on main and pr.
- Setup plan: install xmldiff==3.0 (listed in requirements-dev.txt) on main and pr.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.10
- Installed attrs 26.1.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed black 26.5.1 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed booleanoperations 0.10.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed cffsubr 0.4.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed click 8.4.2 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed coverage 7.15.2 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed defcon 0.12.2 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed execnet 2.1.2 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed flake8 7.3.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed flake8-bugbear 25.11.29 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed fontmath 0.10.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed iniconfig 2.3.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed lxml 6.1.1 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed mccabe 0.7.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed mypy-extensions 1.1.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed packaging 26.2 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pathspec 1.1.1 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed platformdirs 4.11.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pluggy 1.6.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pyclipper 1.4.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pycodestyle 2.14.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pyflakes 3.4.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pygments 2.20.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pytest 9.1.1 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pytest-randomly 4.1.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pytest-xdist 3.8.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed pytokens 0.4.1 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed skia-pathops 0.9.2 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed ufo2ft 3.9.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed ufonormalizer 0.6.3 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed unicodedata2 17.0.1 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.
- Installed xmldiff 3.0 from requirements-dev.txt (listed in requirements-dev.txt) on main and pr.

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (75 unchanged, 3 runs per side) | [pytest-pr-1.log:8](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pytest-pr-1.log) «75 passed in 1.45s» |
| P-C1 | The PR splits comma-separated values in dlng/slng metadata. (PR description) | ⚪ **not testable** | probe model-probe1 has no observation for this claim | no matching log line |

Citation check (WARN): 1 citation(s) verified; 1 statement(s) have no matching log line.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 75 / 75 | - |
| Tests unchanged | 75 | - |
| New tests that pass | 0 | - |
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

**model-probe1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe1.py`, frozen `e00a736d2f09` at 2026-10-22T02:20:49.282235+00:00): Testing meta table handling for dlng/slng splitting and joining

- P-C1 (PR description): The PR splits comma-separated values in dlng/slng metadata. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `testA.input` | - | 🟢 **same on both sides** | same on both sides: `[{"data": " Latn , , Am , ", "tag": "dlng"}]` | [probe-model-probe1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testA.input"»<br>[probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testA.input"» |
| `testA.output` | - | 🟢 **same on both sides** | same on both sides: `{"dlng": ["Latn", "Am"]}` | [probe-model-probe1-main-1.jsonl:2](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testA.output"»<br>[probe-model-probe1-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testA.output"» |
| `testB.input` | - | 🟢 **same on both sides** | same on both sides: `[{"data": "first", "tag": "appl"}, {"data": "second", "tag": "appl"}]` | [probe-model-probe1-main-1.jsonl:3](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testB.input"»<br>[probe-model-probe1-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testB.input"» |
| `testB.output` | - | 🟢 **same on both sides** | same on both sides: `{"appl": "second"}` | [probe-model-probe1-main-1.jsonl:4](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testB.output"»<br>[probe-model-probe1-pr-1.jsonl:4](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testB.output"» |
| `testC.input` | - | 🟢 **same on both sides** | same on both sides: `[{"data": "first", "tag": "bild"}, {"data": "second", "tag": "bild"}]` | [probe-model-probe1-main-1.jsonl:5](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testC.input"»<br>[probe-model-probe1-pr-1.jsonl:5](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testC.input"» |
| `testC.output` | - | 🟢 **same on both sides** | same on both sides: `{"bild": "second"}` | [probe-model-probe1-main-1.jsonl:6](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testC.output"»<br>[probe-model-probe1-pr-1.jsonl:6](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testC.output"» |
| `testD.input` | - | 🟢 **same on both sides** | same on both sides: `[{"data": "A", "tag": "dlng"}, {"data": "B", "tag": "dlng"}]` | [probe-model-probe1-main-1.jsonl:7](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testD.input"»<br>[probe-model-probe1-pr-1.jsonl:7](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testD.input"» |
| `testD.output` | - | 🟢 **same on both sides** | same on both sides: `{"dlng": ["A", "B"]}` | [probe-model-probe1-main-1.jsonl:8](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testD.output"»<br>[probe-model-probe1-pr-1.jsonl:8](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testD.output"» |
| `testE.input` | - | 🟢 **same on both sides** | same on both sides: `[{"data": "X", "tag": "slng"}, {"data": "Y", "tag": "slng"}]` | [probe-model-probe1-main-1.jsonl:9](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testE.input"»<br>[probe-model-probe1-pr-1.jsonl:9](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testE.input"» |
| `testE.output` | - | 🟢 **same on both sides** | same on both sides: `{"slng": ["X", "Y"]}` | [probe-model-probe1-main-1.jsonl:10](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testE.output"»<br>[probe-model-probe1-pr-1.jsonl:10](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testE.output"» |
| `testF.input` | - | 🟢 **same on both sides** | same on both sides: `{"dlng": ["Latn", "Am"]}` | [probe-model-probe1-main-1.jsonl:11](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testF.input"»<br>[probe-model-probe1-pr-1.jsonl:11](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testF.input"» |
| `testF.output` | - | 🟢 **same on both sides** | same on both sides: `[{"data": "Latn, Am", "tag": "dlng"}]` | [probe-model-probe1-main-1.jsonl:12](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testF.output"»<br>[probe-model-probe1-pr-1.jsonl:12](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testF.output"» |
| `testG.input` | - | 🟢 **same on both sides** | same on both sides: `{"appl": "some data"}` | [probe-model-probe1-main-1.jsonl:13](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testG.input"»<br>[probe-model-probe1-pr-1.jsonl:13](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testG.input"» |
| `testG.output` | - | 🟢 **same on both sides** | same on both sides: `[{"data": "some data", "tag": "appl"}]` | [probe-model-probe1-main-1.jsonl:14](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testG.output"»<br>[probe-model-probe1-pr-1.jsonl:14](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testG.output"» |
| `testH.all_stripped` | - | 🟢 **same on both sides** | same on both sides: `true` | [probe-model-probe1-main-1.jsonl:15](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testH.all_stripped"»<br>[probe-model-probe1-pr-1.jsonl:15](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testH.all_stripped"» |
| `testH.non_empty` | - | 🟢 **same on both sides** | same on both sides: `true` | [probe-model-probe1-main-1.jsonl:16](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testH.non_empty"»<br>[probe-model-probe1-pr-1.jsonl:16](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testH.non_empty"» |
| `testI.warning_appl_logged` | - | 🟢 **same on both sides** | same on both sides: `true` | [probe-model-probe1-main-1.jsonl:17](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testI.warning_appl_logged"»<br>[probe-model-probe1-pr-1.jsonl:17](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testI.warning_appl_logged"» |
| `testI.warning_bild_logged` | - | 🟢 **same on both sides** | same on both sides: `true` | [probe-model-probe1-main-1.jsonl:18](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testI.warning_bild_logged"»<br>[probe-model-probe1-pr-1.jsonl:18](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testI.warning_bild_logged"» |
| `testI.warning_dlng_logged` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-model-probe1-main-1.jsonl:19](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testI.warning_dlng_logged"»<br>[probe-model-probe1-pr-1.jsonl:19](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testI.warning_dlng_logged"» |
| `testI.warning_slng_logged` | - | 🟢 **same on both sides** | same on both sides: `false` | [probe-model-probe1-main-1.jsonl:20](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl) «"observation": "testI.warning_slng_logged"»<br>[probe-model-probe1-pr-1.jsonl:20](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl) «"observation": "testI.warning_slng_logged"» |

**diff-api** (diff (auto-derived from base-side code, model-free); informational under baseline full, `diff-probes/diff-api.py`, frozen `78e024ecadae` at 2026-10-22T02:20:49.289862+00:00): Public functions touched by the PR, called with type-appropriate inputs on both sides.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `Lib.glyphsLib.builder.custom_params.to_glyphs_meta_table.import` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ModuleNotFoundError"}` | [probe-diff-api-main-1.jsonl:1](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-diff-api-main-1.jsonl) «"observation": "Lib.glyphsLib.builder.custom_params.to_glyphs_meta_table.import"»<br>[probe-diff-api-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-diff-api-pr-1.jsonl) «"observation": "Lib.glyphsLib.builder.custom_params.to_glyphs_meta_table.import"» |
| `Lib.glyphsLib.builder.custom_params.to_ufo_meta_table.import` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ModuleNotFoundError"}` | [probe-diff-api-main-1.jsonl:2](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-diff-api-main-1.jsonl) «"observation": "Lib.glyphsLib.builder.custom_params.to_ufo_meta_table.import"»<br>[probe-diff-api-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-diff-api-pr-1.jsonl) «"observation": "Lib.glyphsLib.builder.custom_params.to_ufo_meta_table.import"» |

Citation check (PASS): 44 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (3.4 s run).

Coverage gate (python, confidence normal): the changed Python lines are not executable (comments, docstrings, blank lines).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `Lib/glyphsLib/builder/custom_params.py` | 0 | 0 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `3783ef49b506` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: all runs exited 0.
- Changed code was exercised (coverage gate): the changed Python lines are not executable (comments, docstrings, blank lines).
- Probes ran on both sides: 2 probe(s), 3 alternating runs per side, every run printed its observations.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every probe observation cites its output line: 44 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Run did not finish | ⚪ **COULD NOT VERIFY** | could not verify: claim(s) C1 expect a difference but no observation matches (docstring-only change (AST equal after blanking docstrings); behaviour claims hold by construction) | Read the setup/build log under Evidence links; build failures usually need a compiler or a newer nightly. |
| Every claim cites a real log line | 🟠 **WARN** | 1 citation(s) verified; 1 statement(s) have no matching log line | Regenerate the report; if it persists, the logs were edited or truncated. |

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
| Every claim cites a real log line | 🟠 **WARN** | 1 citation(s) verified; 1 statement(s) have no matching log line |
| Every probe observation cites its output line | 🟢 **PASS** | 44 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/glyphslib-1208 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/googlefonts/glyphsLib/pull/1208
```

## Evidence links

- [Pull request googlefonts/glyphsLib#1208](https://github.com/googlefonts/glyphsLib/pull/1208)
- [record.json](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/coverage-pr.json)
- [probe-model-probe1-main-1.jsonl](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-main-1.jsonl)
- [probe-model-probe1-pr-1.jsonl](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-model-probe1-pr-1.jsonl)
- [probe-diff-api-main-1.jsonl](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-diff-api-main-1.jsonl)
- [probe-diff-api-pr-1.jsonl](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/probe-diff-api-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:8](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pytest-main-1.log) «75 passed in 1.46s»
- pr run 1 result: [pytest-pr-1.log:8](../../ops/runs/2026-10-22-check-0748/glyphslib-1208/pytest-pr-1.log) «75 passed in 1.45s»

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
