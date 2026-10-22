# Reviewer report: bopen/elevation#89: Cache missing tiles

Run `elevation-89`, tested 2026-10-22 10:41 IST by ops/daily_run.py (route source-pair). Proof-of-Change commit `0fa0016ea51794edee0f4a085e41bf48dd813765`. Report generated 2026-10-22 10:44 IST by reports/pr_report.py.

Baseline: **full** (test comparison + claim probes + coverage gate + claim flagging (differential probes shown, informational)).

> ## 🟠 NEEDS ATTENTION
>
> **Recommended action:** Reject  
> **Confidence:** High. The run is trustworthy and found a difference a person should look at. Every check passed and every claim cites a log line.
>
> Advice only: Proof-of-Change never blocks a merge and never posts on GitHub.

## Summary in plain English

- **What it says it does:** Cache missing tiles ([bopen/elevation#89](https://github.com/bopen/elevation/pull/89)).
- **What we observed:** probe: 3 observation(s) need attention: exception_type does not differ although the claim says it does (C1); spool_files_count does not differ although the claim says it does (C1); tile_cached_after_ensure does not differ although the claim says it does (C1); probe model-probe1 is not_adequate (no changed executable line exists on the main side (new files, comments or docstrings only), so the probe cannot be shown to reach the change); its matching results do not count; tests: 37 test(s) ran on main, 37 on the PR; 0 new test(s) pass, 32 unchanged; 5 test failure(s) pre-existing and identical on both sides.
- **What you should do:** Do not approve as is. Read 'What changed in behavior' and decide with the PR author.

### Demo helper

These notes are background from the console and the daily check. They do not change the verdict.

If setup fails, the helper retries the install up to 2 times. If a test still can't be verified because something is missing, it installs what's missing and reruns that test once.

- Setup check: GitHub token: present.
- Setup check: Nebius token: present.
- Setup check: free memory 9.0 GB (of 15.6 GB).
- Setup check: free disk 89.1 GB.
- Demo helper: git is installed.
- Demo helper: python3 is installed.
- Demo helper: uv is installed.
- Looked up with Tavily: 5 results
- Query: elevation python setup install instructions https://github.com/bopen/elevation site:github.com/bopen/elevation
- Query: elevation python documentation install https://github.com/bopen/elevation site:github.com/bopen/elevation
- Query: elevation python install requirements https://pypi.org/project/elevation/ https://github.com/bopen/elevation site:pypi.org
- Source: README.rst - bopen/elevation — https://github.com/bopen/elevation/blob/main/README.rst
- Source: elevation · PyPI — https://pypi.org/project/elevation/
- Source: lidar · PyPI — https://pypi.org/project/lidar/
- Source: GitHub - bopen/elevation: Download, cache and clip global terrain digital elevation models: Mapzen terrain tiles, SRTM 30m and 90m DEMs · GitHub — https://github.com/bopen/elevation
- Source: Issue #34 · bopen/elevation - Windows support — https://github.com/bopen/elevation/issues/34
- Setup plan: the same packages on main and pr.
- Setup plan: appdirs is noted, installed with the project.
- Setup plan: fasteners is noted, installed with the project.
- Setup plan: typer is noted, installed with the project.
- Setup plan: Python 3.12: Python 3.12 already meets >=3.11

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C2 | Existing behavior is kept: tests that pass on main still pass (implied by every PR) | 🟢 **proven** | no test that passes on main fails on the PR (37 unchanged, 3 runs per side) | [pytest-pr-1.log:1029](../../ops/runs/2026-10-22-check-1041/elevation-89/pytest-pr-1.log) «5 failed, 32 passed in 1.26s» |
| P-C1 | After the change, missing tiles are cached. (PR description) | 🟠 **not observed** | probe model-probe1, exception_type: same on both sides: `"FileNotFoundError"` | [probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-pr-1.jsonl) «"observation": "exception_type"» |

Citation check (PASS): 2 citation(s), every one re-read from its log file and matched.

## What changed in behavior

| What | Count | Examples |
|---|---|---|
| Tests that actually ran (main / PR, fewest of the runs) | 37 / 37 | - |
| Tests unchanged | 37 | - |
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
| Tests that fail identically on both sides (already broken on main) | 5 | `tests.test_10_spatial::test_call_gdal_translate`, `tests.test_10_spatial::test_call_gdal_translate_empty_on_notfound_local`, `tests.test_10_spatial::test_import_bounds_invalid`, `tests.test_10_spatial::test_import_bounds_raster`, `tests.test_10_spatial::test_import_bounds_vector` |

## Probes

Model-written probes: model provider: nebius (Token Factory, live).

A probe is a small deterministic script run on both sides in the same environments as the tests, 3 alternating runs per side. It prints JSON observations; plain code (poc/diff.py) compares them. A difference that no claim of the PR covers needs attention. Every probe was frozen (content sha256) before any PR-side code ran, and checked against that freeze before each PR-side run. Only a live model probe is blind; fixed probes and recorded model fixtures are known-answer cases.

**model-probe1** (model (nvidia/nemotron-3-super-120b-a12b, live), `model-probes/model-probe1.py`, frozen `d90b2da4df7c` at 2026-10-22T05:14:10.918014+00:00): Test caching behavior of missing tiles

- P-C1 (PR description): After the change, missing tiles are cached. Expects the covered observations to differ.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `exception_type` | P-C1 | 🟠 **no change although the claim says it changes** | same on both sides: `"FileNotFoundError"` | [probe-model-probe1-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-main-1.jsonl) «"observation": "exception_type"»<br>[probe-model-probe1-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-pr-1.jsonl) «"observation": "exception_type"» |
| `spool_files_count` | P-C1 | 🟠 **no change although the claim says it changes** | same on both sides: `0` | [probe-model-probe1-main-1.jsonl:2](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-main-1.jsonl) «"observation": "spool_files_count"»<br>[probe-model-probe1-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-pr-1.jsonl) «"observation": "spool_files_count"» |
| `tile_cached_after_ensure` | P-C1 | 🟠 **no change although the claim says it changes** | same on both sides: `false` | [probe-model-probe1-main-1.jsonl:3](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-main-1.jsonl) «"observation": "tile_cached_after_ensure"»<br>[probe-model-probe1-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-pr-1.jsonl) «"observation": "tile_cached_after_ensure"» |
| `tile_file_size` | - | 🟢 **same on both sides** | same on both sides: `0` | [probe-model-probe1-main-1.jsonl:4](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-main-1.jsonl) «"observation": "tile_file_size"»<br>[probe-model-probe1-pr-1.jsonl:4](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-pr-1.jsonl) «"observation": "tile_file_size"» |

**diff-api** (diff (auto-derived from base-side code, model-free); informational under baseline full, `diff-probes/diff-api.py`, frozen `1a7190729261` at 2026-10-22T05:14:10.934250+00:00): Public functions touched by the PR, called with type-appropriate inputs on both sides.

| Observation | Claim | Result | What the probe saw (main -> PR) | Log lines (main, PR) |
|---|---|---|---|---|
| `elevation.cache.ensure_tiles.input0` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:1](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input0"»<br>[probe-diff-api-pr-1.jsonl:1](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input0"» |
| `elevation.cache.ensure_tiles.input1` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:2](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input1"»<br>[probe-diff-api-pr-1.jsonl:2](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input1"» |
| `elevation.cache.ensure_tiles.input10` | - | 🟢 **same on both sides** | same on both sides: `null` | [probe-diff-api-main-1.jsonl:3](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input10"»<br>[probe-diff-api-pr-1.jsonl:3](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input10"» |
| `elevation.cache.ensure_tiles.input11` | - | 🟢 **same on both sides** | same on both sides: `null` | [probe-diff-api-main-1.jsonl:4](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input11"»<br>[probe-diff-api-pr-1.jsonl:4](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input11"» |
| `elevation.cache.ensure_tiles.input2` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:5](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input2"»<br>[probe-diff-api-pr-1.jsonl:5](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input2"» |
| `elevation.cache.ensure_tiles.input3` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:6](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input3"»<br>[probe-diff-api-pr-1.jsonl:6](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input3"» |
| `elevation.cache.ensure_tiles.input4` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:7](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input4"»<br>[probe-diff-api-pr-1.jsonl:7](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input4"» |
| `elevation.cache.ensure_tiles.input5` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:8](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input5"»<br>[probe-diff-api-pr-1.jsonl:8](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input5"» |
| `elevation.cache.ensure_tiles.input6` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:9](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input6"»<br>[probe-diff-api-pr-1.jsonl:9](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input6"» |
| `elevation.cache.ensure_tiles.input7` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:10](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input7"»<br>[probe-diff-api-pr-1.jsonl:10](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input7"» |
| `elevation.cache.ensure_tiles.input8` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:11](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input8"»<br>[probe-diff-api-pr-1.jsonl:11](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input8"» |
| `elevation.cache.ensure_tiles.input9` | - | 🟢 **same on both sides** | same on both sides: `null` | [probe-diff-api-main-1.jsonl:12](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input9"»<br>[probe-diff-api-pr-1.jsonl:12](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.ensure_tiles.input9"» |
| `elevation.cache.is_cached.input0` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:13](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input0"»<br>[probe-diff-api-pr-1.jsonl:13](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input0"» |
| `elevation.cache.is_cached.input1` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:14](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input1"»<br>[probe-diff-api-pr-1.jsonl:14](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input1"» |
| `elevation.cache.is_cached.input10` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:15](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input10"»<br>[probe-diff-api-pr-1.jsonl:15](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input10"» |
| `elevation.cache.is_cached.input11` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:16](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input11"»<br>[probe-diff-api-pr-1.jsonl:16](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input11"» |
| `elevation.cache.is_cached.input2` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:17](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input2"»<br>[probe-diff-api-pr-1.jsonl:17](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input2"» |
| `elevation.cache.is_cached.input3` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:18](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input3"»<br>[probe-diff-api-pr-1.jsonl:18](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input3"» |
| `elevation.cache.is_cached.input4` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:19](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input4"»<br>[probe-diff-api-pr-1.jsonl:19](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input4"» |
| `elevation.cache.is_cached.input5` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:20](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input5"»<br>[probe-diff-api-pr-1.jsonl:20](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input5"» |
| `elevation.cache.is_cached.input6` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:21](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input6"»<br>[probe-diff-api-pr-1.jsonl:21](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input6"» |
| `elevation.cache.is_cached.input7` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:22](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input7"»<br>[probe-diff-api-pr-1.jsonl:22](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input7"» |
| `elevation.cache.is_cached.input8` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:23](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input8"»<br>[probe-diff-api-pr-1.jsonl:23](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input8"» |
| `elevation.cache.is_cached.input9` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:24](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.cache.is_cached.input9"»<br>[probe-diff-api-pr-1.jsonl:24](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.cache.is_cached.input9"» |
| `elevation.datasource.seed.input0` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "TypeError"}` | [probe-diff-api-main-1.jsonl:25](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.datasource.seed.input0"»<br>[probe-diff-api-pr-1.jsonl:25](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.datasource.seed.input0"» |
| `elevation.spatial.call_gdal_translate.input0` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:26](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input0"»<br>[probe-diff-api-pr-1.jsonl:26](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input0"» |
| `elevation.spatial.call_gdal_translate.input1` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:27](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input1"»<br>[probe-diff-api-pr-1.jsonl:27](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input1"» |
| `elevation.spatial.call_gdal_translate.input10` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:28](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input10"»<br>[probe-diff-api-pr-1.jsonl:28](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input10"» |
| `elevation.spatial.call_gdal_translate.input11` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:29](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input11"»<br>[probe-diff-api-pr-1.jsonl:29](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input11"» |
| `elevation.spatial.call_gdal_translate.input2` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:30](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input2"»<br>[probe-diff-api-pr-1.jsonl:30](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input2"» |
| `elevation.spatial.call_gdal_translate.input3` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:31](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input3"»<br>[probe-diff-api-pr-1.jsonl:31](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input3"» |
| `elevation.spatial.call_gdal_translate.input4` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:32](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input4"»<br>[probe-diff-api-pr-1.jsonl:32](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input4"» |
| `elevation.spatial.call_gdal_translate.input5` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:33](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input5"»<br>[probe-diff-api-pr-1.jsonl:33](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input5"» |
| `elevation.spatial.call_gdal_translate.input6` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:34](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input6"»<br>[probe-diff-api-pr-1.jsonl:34](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input6"» |
| `elevation.spatial.call_gdal_translate.input7` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:35](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input7"»<br>[probe-diff-api-pr-1.jsonl:35](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input7"» |
| `elevation.spatial.call_gdal_translate.input8` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:36](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input8"»<br>[probe-diff-api-pr-1.jsonl:36](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input8"» |
| `elevation.spatial.call_gdal_translate.input9` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:37](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input9"»<br>[probe-diff-api-pr-1.jsonl:37](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.call_gdal_translate.input9"» |
| `elevation.spatial.gdal_json.input0` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:38](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input0"»<br>[probe-diff-api-pr-1.jsonl:38](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input0"» |
| `elevation.spatial.gdal_json.input1` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:39](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input1"»<br>[probe-diff-api-pr-1.jsonl:39](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input1"» |
| `elevation.spatial.gdal_json.input10` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:40](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input10"»<br>[probe-diff-api-pr-1.jsonl:40](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input10"» |
| `elevation.spatial.gdal_json.input11` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:41](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input11"»<br>[probe-diff-api-pr-1.jsonl:41](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input11"» |
| `elevation.spatial.gdal_json.input2` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:42](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input2"»<br>[probe-diff-api-pr-1.jsonl:42](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input2"» |
| `elevation.spatial.gdal_json.input3` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:43](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input3"»<br>[probe-diff-api-pr-1.jsonl:43](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input3"» |
| `elevation.spatial.gdal_json.input4` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "FileNotFoundError"}` | [probe-diff-api-main-1.jsonl:44](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input4"»<br>[probe-diff-api-pr-1.jsonl:44](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input4"» |
| `elevation.spatial.gdal_json.input5` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:45](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input5"»<br>[probe-diff-api-pr-1.jsonl:45](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input5"» |
| `elevation.spatial.gdal_json.input6` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:46](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input6"»<br>[probe-diff-api-pr-1.jsonl:46](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input6"» |
| `elevation.spatial.gdal_json.input7` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:47](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input7"»<br>[probe-diff-api-pr-1.jsonl:47](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input7"» |
| `elevation.spatial.gdal_json.input8` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "AttributeError"}` | [probe-diff-api-main-1.jsonl:48](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input8"»<br>[probe-diff-api-pr-1.jsonl:48](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input8"» |
| `elevation.spatial.gdal_json.input9` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "PermissionError"}` | [probe-diff-api-main-1.jsonl:49](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.gdal_json.input9"»<br>[probe-diff-api-pr-1.jsonl:49](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.gdal_json.input9"» |
| `elevation.spatial.is_not_found.input0` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:50](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input0"»<br>[probe-diff-api-pr-1.jsonl:50](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input0"» |
| `elevation.spatial.is_not_found.input1` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:51](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input1"»<br>[probe-diff-api-pr-1.jsonl:51](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input1"» |
| `elevation.spatial.is_not_found.input10` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:52](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input10"»<br>[probe-diff-api-pr-1.jsonl:52](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input10"» |
| `elevation.spatial.is_not_found.input11` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:53](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input11"»<br>[probe-diff-api-pr-1.jsonl:53](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input11"» |
| `elevation.spatial.is_not_found.input2` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:54](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input2"»<br>[probe-diff-api-pr-1.jsonl:54](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input2"» |
| `elevation.spatial.is_not_found.input3` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:55](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input3"»<br>[probe-diff-api-pr-1.jsonl:55](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input3"» |
| `elevation.spatial.is_not_found.input4` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:56](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input4"»<br>[probe-diff-api-pr-1.jsonl:56](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input4"» |
| `elevation.spatial.is_not_found.input5` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:57](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input5"»<br>[probe-diff-api-pr-1.jsonl:57](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input5"» |
| `elevation.spatial.is_not_found.input6` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:58](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input6"»<br>[probe-diff-api-pr-1.jsonl:58](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input6"» |
| `elevation.spatial.is_not_found.input7` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:59](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input7"»<br>[probe-diff-api-pr-1.jsonl:59](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input7"» |
| `elevation.spatial.is_not_found.input8` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:60](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input8"»<br>[probe-diff-api-pr-1.jsonl:60](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input8"» |
| `elevation.spatial.is_not_found.input9` | - | 🟢 **same on both sides** | same on both sides: `{"raises": "ValueError"}` | [probe-diff-api-main-1.jsonl:61](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl) «"observation": "elevation.spatial.is_not_found.input9"»<br>[probe-diff-api-pr-1.jsonl:61](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl) «"observation": "elevation.spatial.is_not_found.input9"» |

Citation check (PASS): 130 citation(s), every one re-read from its log file and matched.

## Was the changed code exercised?

**Coverage: MEASURED** by coverage.py on the PR side (2.6 s run).

Coverage gate (python, confidence normal): the changed Python lines are not executable (comments, docstrings, blank lines).

| Changed file | Changed executable lines | Of those, ran |
|---|---|---|
| `elevation/cache.py` | 0 | 0 |
| `elevation/datasource.py` | 0 | 0 |
| `elevation/spatial.py` | 0 | 0 |

How this is measured: one extra, untimed run of the PR side's tests under coverage.py. Changed lines come from comparing the tested main and PR files. Compiled code (C, C++, Cython) is invisible to coverage.py; such a change only counts as verified when the PR adds or changes a test for that module.

## What went right

- Tested `f94e513fa302` of the PR against main (source-pair route).
- 3 alternating runs per side: main 3, PR 3 of 3.
- pytest exit codes explained: pytest exit 1; 5 failure(s)/error(s) pre-existing and identical on both sides.
- Changed code was exercised (coverage gate): the changed Python lines are not executable (comments, docstrings, blank lines).
- Probes ran on both sides: 2 probe(s), 3 alternating runs per side, every run printed its observations.
- Single-thread environment: OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0.
- Machine type recorded: local x86_64 8 cpus.
- Nothing posted upstream: GitHub was only read.
- Every claim cites a real log line: 2 citation(s), every one re-read from its log file and matched.
- Every probe observation cites its output line: 130 citation(s), every one re-read from its log file and matched.

## What went wrong and how to fix it

| Issue | Status | Detail | How to fix |
|---|---|---|---|
| Behavior difference found | 🟠 **finding** | probe: 3 observation(s) need attention: exception_type does not differ although the claim says it does (C1); spool_files_count does not differ although the claim says it does (C1); tile_cached_after_ensure does not differ although the claim says it does (C1); probe model-probe1 is not_adequate (no changed executable line exists on the main side (new files, comments or docstrings only), so the probe cannot be shown to reach the change); its matching results do not count; tests: 37 test(s) ran on main, 37 on the PR; 0 new test(s) pass, 32 unchanged; 5 test failure(s) pre-existing and identical on both sides | This is about the PR, not the run: read the failing tests and their log lines and the Probes section, then decide. |

## Evals and guardrails

| Check | Result | Detail |
|---|---|---|
| 3 alternating runs per side | 🟢 **PASS** | main 3, PR 3 of 3 |
| pytest exit codes explained | 🟢 **PASS** | pytest exit 1; 5 failure(s)/error(s) pre-existing and identical on both sides |
| Changed code was exercised (coverage gate) | 🟢 **PASS** | the changed Python lines are not executable (comments, docstrings, blank lines) |
| Probes ran on both sides | 🟢 **PASS** | 2 probe(s), 3 alternating runs per side, every run printed its observations |
| Single-thread environment | 🟢 **PASS** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1, PYTHONHASHSEED=0 |
| Machine type recorded | 🟢 **PASS** | local x86_64 8 cpus |
| Nothing posted upstream | 🟢 **PASS** | GitHub was only read |
| Known-answer replay (fresh re-run) | ⚪ **SKIP** | not replayed yet |
| Every claim cites a real log line | 🟢 **PASS** | 2 citation(s), every one re-read from its log file and matched |
| Every probe observation cites its output line | 🟢 **PASS** | 130 citation(s), every one re-read from its log file and matched |

## Checklist

- [ ] I read the verdict and the plain-English summary.
- [ ] Every 'false' or 'unmentioned change' row has a log line I can open.
- [ ] Nothing under 'What went wrong' is a run problem (those mean Re-run, not Reject).
- [ ] I recorded my decision (see below).

**Decision recorded:** none yet. To record one, run `make decide REPORT=<run>/report/elevation-89 DECISION=approve` (or `reject`, `approve_with_notes`, `re_run`).

## Rerun command

```
make check PR=https://github.com/bopen/elevation/pull/89
```

## Evidence links

- [Pull request bopen/elevation#89](https://github.com/bopen/elevation/pull/89)
- [record.json](../../ops/runs/2026-10-22-check-1041/elevation-89/record.json)
- [pr.diff](../../ops/runs/2026-10-22-check-1041/elevation-89/pr.diff)
- [setup-main.log](../../ops/runs/2026-10-22-check-1041/elevation-89/setup-main.log)
- [setup-pr.log](../../ops/runs/2026-10-22-check-1041/elevation-89/setup-pr.log)
- [git.log](../../ops/runs/2026-10-22-check-1041/elevation-89/git.log)
- [pytest-main-1.log](../../ops/runs/2026-10-22-check-1041/elevation-89/pytest-main-1.log)
- [pytest-pr-1.log](../../ops/runs/2026-10-22-check-1041/elevation-89/pytest-pr-1.log)
- [pytest-main-2.log](../../ops/runs/2026-10-22-check-1041/elevation-89/pytest-main-2.log)
- [pytest-pr-2.log](../../ops/runs/2026-10-22-check-1041/elevation-89/pytest-pr-2.log)
- [pytest-main-3.log](../../ops/runs/2026-10-22-check-1041/elevation-89/pytest-main-3.log)
- [pytest-pr-3.log](../../ops/runs/2026-10-22-check-1041/elevation-89/pytest-pr-3.log)
- [junit-main-1.xml](../../ops/runs/2026-10-22-check-1041/elevation-89/junit-main-1.xml)
- [junit-pr-1.xml](../../ops/runs/2026-10-22-check-1041/elevation-89/junit-pr-1.xml)
- [coverage-pytest.log](../../ops/runs/2026-10-22-check-1041/elevation-89/coverage-pytest.log)
- [coverage-pr.json](../../ops/runs/2026-10-22-check-1041/elevation-89/coverage-pr.json)
- [probe-model-probe1-main-1.jsonl](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-main-1.jsonl)
- [probe-model-probe1-pr-1.jsonl](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-model-probe1-pr-1.jsonl)
- [probe-diff-api-main-1.jsonl](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-main-1.jsonl)
- [probe-diff-api-pr-1.jsonl](../../ops/runs/2026-10-22-check-1041/elevation-89/probe-diff-api-pr-1.jsonl)
- main run 1 result: [pytest-main-1.log:1029](../../ops/runs/2026-10-22-check-1041/elevation-89/pytest-main-1.log) «5 failed, 32 passed in 1.22s»
- pr run 1 result: [pytest-pr-1.log:1029](../../ops/runs/2026-10-22-check-1041/elevation-89/pytest-pr-1.log) «5 failed, 32 passed in 1.26s»

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
