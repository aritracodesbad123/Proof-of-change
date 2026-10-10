# Reviewer report: pandas 2.3.3 to 3.0.0rc0 (contains PR #56633)

Run `golden-pandas300rc0-upsetplot090`, tested against UpSetPlot 0.9.0. Report generated 2026-10-10 05:53 IST by reports/generate.py 1.0 (from Jonathan's render_report.py 0.1).

> ## 🟠 NEEDS ATTENTION
>
> **Recommended action:** Reject  
> **Confidence:** High. All required checks and evals passed, 3 runs per side gave identical results (stability old 1.0, new 1.0), 3 of 3 golden cases hold, tests ran without network.
>
> Scope: this run compares two released versions, not a single PR's commits. Any change between the two versions can cause what is shown here.

## Summary in plain English

- **What it says it does:** PR #56633 "CoW: Enable CoW by default and remove warning build" makes Copy-on-Write the default (PR title, github.com/pandas-dev/pandas/pull/56633, verified via the GitHub API on 2026-10-10).
- **What we observed:** 67 test(s) of UpSetPlot that passed with pandas 2.3.3 fail with pandas 3.0.0rc0, in 5 distinct error type(s). Same result in all 3 runs on each side. 6 test(s) already failed before the change and are not counted.
- **What you should do:** Do not approve as is. The change breaks UpSetPlot; see 'What changed in behavior' for what fails.

## Claims vs reality

| # | Claim (source) | Status | What we observed | Log line |
|---|---|---|---|---|
| C1 | Copy-on-Write is enabled by default (PR #56633 title) | ⚪ **not testable** | the dependent's tests do not check the pandas setting itself; they show its effect on dependent code | [pytest-new-1.log:2104](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «Invalid RGBA argument: nan» |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 36 test(s) now fail with: ValueError: Invalid RGBA argument: nan (linked to C1 by UpSetPlot issue #303 (github.com/jnothman/UpSetPlot/issues/303)) | [pytest-new-1.log:2104](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: Invalid RGBA argument: nan» |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 16 test(s) now fail with: AssertionError: DataFrame.index level [N] are different (no claim mentions this) | [pytest-new-1.log:35](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «AssertionError: DataFrame.index level [» |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 13 test(s) now fail with: ValueError: Do not know how to convert N    NaN (no claim mentions this) | [pytest-new-1.log:2510](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: Do not know how to convert» |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 1 test(s) now fail with: ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N     #0000002e (no claim mentions this) | [pytest-new-1.log:9372](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not» |
| - | Change not in the PR description (this run) | 🟠 **unmentioned change** | 1 test(s) now fail with: ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N           NaN (no claim mentions this) | [pytest-new-1.log:9372](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not» |

Citation check (PASS): 6 claim(s), every one backed by a real log line

## What changed in behavior

67 real break(s) in 5 group(s), largest first.

| # | Error after the change | Tests | Log line |
|---|---|---|---|
| 1 | ValueError: Invalid RGBA argument: nan | 36 | [pytest-new-1.log:2104](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: Invalid RGBA argument: nan» |
| 2 | AssertionError: DataFrame.index level [N] are different | 16 | [pytest-new-1.log:35](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «AssertionError: DataFrame.index level [» |
| 3 | ValueError: Do not know how to convert N    NaN | 13 | [pytest-new-1.log:2510](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: Do not know how to convert» |
| 4 | ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N     #0000002e | 1 | [pytest-new-1.log:9372](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not» |
| 5 | ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N           NaN | 1 | [pytest-new-1.log:9372](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not» |

### Group 1: 36 test(s)

**Error:** ValueError: Invalid RGBA argument: nan

**Affected tests:** `test_add_stacked_bars[False-horizontal]`, `test_add_stacked_bars[False-vertical]`, `test_add_stacked_bars[True-horizontal]`, `test_add_stacked_bars[True-vertical]`, `test_add_stacked_bars_colors[<lambda>-expected4]`, `test_add_stacked_bars_colors[Pastel1-expected2]`, and 30 more (full list: [class-real_break.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-real_break.txt))

**Example:** `upsetplot.tests.test_upsetplot::test_add_stacked_bars[False-horizontal]`. Before: passed, passed, passed (old runs). After: failed, failed, failed (new runs).

```
Before (old side): test passed, no error output

After (new side):
ValueError: Invalid RGBA argument: nan
```

### Group 2: 16 test(s)

**Error:** AssertionError: DataFrame.index level [N] are different

**Affected tests:** `test_from_contents_vs_memberships[blah-iter-None]`, `test_from_contents_vs_memberships[blah-iter-data1]`, `test_from_contents_vs_memberships[blah-list-None]`, `test_from_contents_vs_memberships[blah-list-data1]`, `test_from_contents_vs_memberships[blah-set-None]`, `test_from_contents_vs_memberships[blah-set-data1]`, and 10 more (full list: [class-real_break.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-real_break.txt))

**Example:** `upsetplot.tests.test_data::test_from_contents_vs_memberships[blah-iter-None]`. Before: passed, passed, passed (old runs). After: failed, failed, failed (new runs).

```
Before (old side): test passed, no error output

After (new side):
AssertionError: DataFrame.index level [0] are different
Attribute "dtype" are different
[left]:  object
[right]: bool
```

### Group 3: 13 test(s)

**Error:** ValueError: Do not know how to convert N    NaN

**Affected tests:** `test_two_sets[set20-set11]`, `test_two_sets[set20-set12]`, `test_two_sets[set21-set10]`, `test_two_sets[set21-set11]`, `test_two_sets[set21-set12]`, `test_two_sets[set21-set13]`, and 7 more (full list: [class-real_break.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-real_break.txt))

**Example:** `upsetplot.tests.test_upsetplot::test_two_sets[set20-set11]`. Before: passed, passed, passed (old runs). After: failed, failed, failed (new runs).

```
Before (old side): test passed, no error output

After (new side):
ValueError: The truth value of a Series is ambiguous. Use a.empty, a.bool(), a.item(), a.any() or a.all().
ValueError: Unrecognized linestyle: nan
ValueError: Do not know how to convert 0    NaN
1    NaN
2    NaN
3    NaN
Name: linestyles, dtype: object to dashes
```

### Group 4: 1 test(s)

**Error:** ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N     #0000002e

**Affected tests:** `test_style_subsets_artists[horizontal]` (full list: [class-real_break.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-real_break.txt))

**Example:** `upsetplot.tests.test_upsetplot::test_style_subsets_artists[horizontal]`. Before: passed, passed, passed (old runs). After: failed, failed, failed (new runs).

```
Before (old side): test passed, no error output

After (new side):
17         blue
18    #0000002e
19         blue
20         blue
21          NaN
22          NaN
23          NaN
Name: facecolors, dtype: object
```

### Group 5: 1 test(s)

**Error:** ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N           NaN

**Affected tests:** `test_style_subsets_artists[vertical]` (full list: [class-real_break.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-real_break.txt))

**Example:** `upsetplot.tests.test_upsetplot::test_style_subsets_artists[vertical]`. Before: passed, passed, passed (old runs). After: failed, failed, failed (new runs).

```
Before (old side): test passed, no error output

After (new side):
17    #0000002e
18          red
19    #0000002e
20    #0000002e
21    #0000002e
22    #0000002e
23    #0000002e
Name: facecolors, dtype: object
```

## What went right

| Status | Check | Detail |
|---|---|---|
| 🟢 **pass** | Correct versions installed | old pandas==2.3.3, new pandas==3.0.0rc0, UpSetPlot==0.9.0 on both sides (freeze + import probe) |
| 🟢 **pass** | Only the upstream version differs between sides | freeze diff: ['pandas==2.3.3', 'pandas==3.0.0rc0'] |
| 🟢 **pass** | Isolated environments | both venvs created by uv without system site-packages (checked sys.prefix and sys.path) |
| 🟢 **pass** | Thread count pinned to 1 | OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS, NUMEXPR_NUM_THREADS, VECLIB_MAXIMUM_THREADS, BLIS_NUM_THREADS = 1 in both envs |
| 🟢 **pass** | All runs completed | 3 runs per side requested (minimum 3); JUnit XML present and no suite timeout on every run |
| 🟢 **pass** | Old side healthy (baseline is trustworthy) | dependent imports on old: {'upsetplot': 'ok'}; old side passed [233, 233, 233] tests with collection errors [0, 0, 0] |
| 🟢 **pass** | Repeatable results | share of tests with the same outcome in every run: old 1.0, new 1.0 (advisory threshold 0.99) |
| 🟢 **pass** | No secrets in logs | scrubbed env; no credential-like strings found in logs |
| 🟢 **pass** | Record format valid | record matches harness/schema/observation.schema.json |
| 🟢 **pass** | Runs per side | 3 (minimum 3), alternating old and new |
| 🟢 **pass** | Guardrails respected | tests ran with no network; nothing was posted or filed by the runner |
| 🟢 **pass** | Matches the prediction written before the run | break: 67 real breaks from Copy-on-Write (Invalid RGBA argument: nan) and 6 already broken (pytest.warns(None)) |
| 🟢 **pass** | Nathan's evals | 6 of 7 eval checks passed (see 'Evals and guardrails') |
| 🟢 **pass** | Every claim cites a log line | 6 claim(s), every one backed by a real log line |

## What went wrong and how to fix it

### Issues in the PR or release

| Issue | How to fix |
|---|---|
| Group 1: 36 test(s) fail with: ValueError: Invalid RGBA argument: nan | Decide whether this change is intended. If yes, document it as a breaking change and tell UpSetPlot; if not, fix it in the PR. Reproduce with the rerun command below and the example test. |
| Group 2: 16 test(s) fail with: AssertionError: DataFrame.index level [N] are different | Decide whether this change is intended. If yes, document it as a breaking change and tell UpSetPlot; if not, fix it in the PR. Reproduce with the rerun command below and the example test. |
| Group 3: 13 test(s) fail with: ValueError: Do not know how to convert N    NaN | Decide whether this change is intended. If yes, document it as a breaking change and tell UpSetPlot; if not, fix it in the PR. Reproduce with the rerun command below and the example test. |
| Group 4: 1 test(s) fail with: ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N     #0000002e | Decide whether this change is intended. If yes, document it as a breaking change and tell UpSetPlot; if not, fix it in the PR. Reproduce with the rerun command below and the example test. |
| Group 5: 1 test(s) fail with: ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N           NaN | Decide whether this change is intended. If yes, document it as a breaking change and tell UpSetPlot; if not, fix it in the PR. Reproduce with the rerun command below and the example test. |

### Issues in our test environment

| Issue | How to fix |
|---|---|
| 6 test(s) of UpSetPlot already fail before the change: TypeError: exceptions must be derived from Warning, not <class 'NoneType'> (6) | Not caused by this change; ignore for this decision. To clean up the baseline, pin the tool versions UpSetPlot expects or deselect these tests (record it in subset_note). |

## Trust checks

| Check | Status | Detail |
|---|---|---|
| Required checks (gates) | 🟢 **7 of 7 passed** | all passed |
| Advisory checks | 🟢 **2 of 2 passed** | all passed |
| Evals (Nathan) | 🟢 **APPROVE** | no failures or warnings |
| Golden cases (stored records) | 🟢 **3 of 3 hold** | checked against the stored golden records (harness 1.0) with the eval gate's code, not re-run for this report. This run is itself one of the golden cases, so this check is partly circular for it |
| Golden cases (re-run) | ⚪ **not available** | no golden re-run recorded in this record (golden_check) |
| Report citations | 🟢 **pass** | 6 claim(s), every one backed by a real log line |
| Flaky rate | 🟢 **0 of 251 (0.0%)** | stability old 1.0, new 1.0 |
| Network during tests | 🟢 **off** | install: allowed (uv from PyPI/nightly index, git clone of the tag); tests: no network (unshare -rn, private network namespace) |
| Threads | 🟢 **pinned to 1** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1 |
| Machine | 🔵 **box** | Intel(R) Xeon(R) Processor, 8 CPUs, 15.6 GB RAM, Linux x86_64, CI: not available |
| Report matches the record | 🟢 **consistent** | break and import-failure counts recomputed from class-*.txt and JUnit equal the record |
| Prediction before the run | 🟢 **yes** | break: 67 real breaks from Copy-on-Write (Invalid RGBA argument: nan) and 6 already broken (pytest.warns(None)) |

| Golden case | Status | Detail |
|---|---|---|
| golden-sklearn160rc1-imblearn-import-failure | 🟢 **holds** | golden-sklearn160rc1-imblearn-import-failure: all expected values hold |
| golden-pandas300rc0-upsetplot-cow | 🟢 **holds** | golden-pandas300rc0-upsetplot-cow: all expected values hold |
| golden-clean-sklearn151-152-imblearn | 🟢 **holds** | golden-clean-sklearn151-152-imblearn: all expected values hold |

## Evals and guardrails (Nathan)

Independent checks of this record by evals/checks.py and guardrails/schema.py against the shared schema `blast-radius/observation/v1` (written against rev 1 (sha256 5a3c3d36b773...); valid under current rev 2 (additive)). Eval recommendation: **APPROVE**. Any FAIL here makes the verdict COULD NOT VERIFY.

| Check | Status | Detail | How to fix |
|---|---|---|---|
| schema | 🟢 **pass** | record matches the shared schema blast-radius/observation/v1, mode v1 (schema reference verified by sha256) | - |
| versions_installed | 🟢 **pass** | pandas 2.3.3 -> 3.0.0rc0; env differs only in pandas | - |
| runs_per_side | 🟢 **pass** | 3 alternating runs per side, identical counts within each side | - |
| single_thread | 🟢 **pass** | OMP/OPENBLAS/MKL_NUM_THREADS=1 | - |
| matches_expected | 🟢 **pass** | outcome matches the prediction written before the run (break) | - |
| golden:golden-pandas300rc0-upsetplot-cow | 🟢 **pass** | golden-pandas300rc0-upsetplot-cow: all expected values hold | - |
| llm_citations | ⚪ **skip** | no Nemotron explanations in this record yet | - |
| report_citations | 🟢 **pass** | 6 claim(s), every one backed by a real log line | - |

## Reviewer checklist

- [ ] I read the verdict, the recommended action and the confidence.
- [ ] I checked the claims vs reality table for any 'false' or 'unmentioned change' rows, and opened at least one cited log line.
- [ ] I looked at the largest behavior-change group and its example error.
- [ ] I confirmed the required checks and Nathan's evals passed (Trust checks, Evals and guardrails).
- [ ] I am satisfied the environment issues (if any) do not change the decision.

**Decision:** ☐ Approve ☐ Approve with notes ☐ Reject ☐ Re-run    Reviewer: ________  Date: ________

## Rerun command

From the blast-radius repo root. The wrapper forces 3 alternating runs per side and the single-thread env, records machine_type, writes under ./data and never posts anything:

```
BR_RUNNER=/workspace/blast-radius-research/harness/br_run.py python -m harness.run \
  --upstream pandas \
  --old 2.3.3 \
  --new 3.0.0rc0 \
  --dependent UpSetPlot \
  --dep-version 0.9.0 \
  --tests repo:https://github.com/jnothman/UpSetPlot:upsetplot/tests \
  --extra-pkgs 'numpy==2.3.5 matplotlib==3.10.8 pytest==9.1.1' \
  --cpus 4-7 \
  --expected 'break: 67 real breaks from Copy-on-Write (Invalid RGBA argument: nan) and 6 already broken (pytest.warns(None))' \
  --expected-class break \
  --id golden-pandas300rc0-upsetplot090-rerun
```

Needs Linux x86_64, uv 0.12 or newer, git and unshare.

## Evidence links

| What | Link (relative to this report) |
|---|---|
| Where the description comes from | PR title, github.com/pandas-dev/pandas/pull/56633, verified via the GitHub API on 2026-10-10 |
| Claim C1 | [pytest-new-1.log:2104](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «Invalid RGBA argument: nan» |
| Unmentioned change | [pytest-new-1.log:2104](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: Invalid RGBA argument: nan» |
| Unmentioned change | [pytest-new-1.log:35](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «AssertionError: DataFrame.index level [» |
| Unmentioned change | [pytest-new-1.log:2510](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: Do not know how to convert» |
| Unmentioned change | [pytest-new-1.log:9372](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not» |
| Unmentioned change | [pytest-new-1.log:9372](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not» |
| pytest summary, old side run 1 | [pytest-old-1.log:475](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-old-1.log) «6 failed, 233 passed, 12 skipped, 414 warnings in 6.59s» |
| pytest summary, new side run 1 | [pytest-new-1.log:10087](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log) «73 failed, 166 passed, 12 skipped, 212 warnings in 10.62s» |
| Full record | [record.json](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/record.json) |
| Run arguments | [args.json](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/args.json) |
| Setup log | [setup.log](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/setup.log) |
| Installed packages, old | [freeze-old.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/freeze-old.txt) |
| Installed packages, new | [freeze-new.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/freeze-new.txt) |
| Package difference | [freeze-diff.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/freeze-diff.txt) |
| pytest logs | [pytest-new-1.log](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-1.log), [pytest-new-2.log](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-2.log), [pytest-new-3.log](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-new-3.log), [pytest-old-1.log](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-old-1.log), [pytest-old-2.log](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-old-2.log), [pytest-old-3.log](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/pytest-old-3.log) |
| JUnit XML | [junit-new-1.xml](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/junit-new-1.xml), [junit-new-2.xml](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/junit-new-2.xml), [junit-new-3.xml](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/junit-new-3.xml), [junit-old-1.xml](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/junit-old-1.xml), [junit-old-2.xml](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/junit-old-2.xml), [junit-old-3.xml](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/junit-old-3.xml) |
| Test lists per class | [class-already_broken.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-already_broken.txt), [class-fixed_by_new.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-fixed_by_new.txt), [class-flaky.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-flaky.txt), [class-import_failure.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-import_failure.txt), [class-lost_tests.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-lost_tests.txt), [class-real_break.txt](../../../../../blast-radius-research/research/runs/golden-pandas300rc0-upsetplot090/class-real_break.txt) |

## Appendix

### Commits and versions

| Item | Value |
|---|---|
| PR | not available |
| PR base / head / merge commit | not available |
| Upstream | pandas: old 2.3.3, new 3.0.0rc0 (requested 3.0.0rc0) |
| Upstream commits (old / new) | PyPI release wheels (no commit recorded) |
| Dependent | UpSetPlot 0.9.0 |
| Tests from | repo tag 0.9.0 (https://github.com/jnothman/UpSetPlot, commit 7d889a9df7974509965a5ffd313e27764d43322a); selection: upsetplot/tests |
| Python | 3.13.5 |
| Environment difference | pandas==2.3.3, pandas==3.0.0rc0 |
| Runner | harness 1.0, 4 workers, import mode importlib, per-test timeout 300 s, memory cap 6.0 GB |
| Record schema | v1; written against rev 1 (sha256 5a3c3d36b773...); valid under current rev 2 (additive) |
| Run by | Jonathan on box, 2026-10-10 05:36 IST |
| Hand check | not available |
| Upstream issue | not available |
| Per-test outcomes | not available |
| AI explanation | not yet wired |

### Timings

Total wall time 56.5 s; mean test time old 7.3 s, new 9.8 s.

| Side | Run | Exit | Seconds | pytest summary |
|---|---|---|---|---|
| old | 1 | 1 | 7.19 | 6 failed, 233 passed, 12 skipped, 414 warnings in 6.59s |
| new | 1 | 1 | 11.4 | 73 failed, 166 passed, 12 skipped, 212 warnings in 10.62s |
| old | 2 | 1 | 8.16 | 6 failed, 233 passed, 12 skipped, 414 warnings in 7.62s |
| new | 2 | 1 | 8.75 | 73 failed, 166 passed, 12 skipped, 212 warnings in 8.20s |
| old | 3 | 1 | 6.58 | 6 failed, 233 passed, 12 skipped, 414 warnings in 6.00s |
| new | 3 | 1 | 9.16 | 73 failed, 166 passed, 12 skipped, 212 warnings in 8.55s |

## Glossary

| Term | Meaning |
|---|---|
| Old side / new side | The same dependent library tested twice: once with the old version of the upstream library, once with the new one. Nothing else differs. |
| Upstream | The library being changed (for example pandas). The PR or release under review belongs to it. |
| Dependent | A library that uses the upstream. Its own tests are our test subject. |
| Real break | A test that passed in every old run and failed in every new run. This is a behavior change caused by the upstream change. |
| Import failure | A test module that cannot even be loaded on the new side, so none of its tests can run. Counted per module. |
| Lost tests | Tests that passed before but could not run after, because their module failed to load. Not counted as real breaks. |
| Already broken | Tests that failed before the change too. Not caused by the change. |
| Flaky | Tests whose result changes between runs on the same side. They are not trusted either way. |
| Error signature | The error message with numbers and file paths removed, so identical failures group together. |
| Gate | An automatic check by the runner that the run itself is trustworthy (right versions, same environment, enough runs). Required gates must pass for the result to count. |
| Eval | Nathan's independent check of the record (schema, versions, runs per side, threads, golden cases, citations). Any eval failure means the run cannot be trusted. |
| Golden case | A known example with a known answer. If the tool still gets the golden cases right, its answers on new cases are more believable. |
| Stability | Share of tests that gave the same result in every run on one side. 1.0 means fully repeatable. |
| Citation | A file name, line number and quoted text from a run log that backs a statement in the report. |
| JUnit XML | The machine-readable test result file pytest writes for each run. |
| Freeze | The exact list of installed packages and versions on each side. |
