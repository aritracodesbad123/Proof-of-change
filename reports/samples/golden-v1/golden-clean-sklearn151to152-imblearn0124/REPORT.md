# Reviewer report: scikit-learn 1.5.1 to 1.5.2

Run `golden-clean-sklearn151to152-imblearn0124`, tested against imbalanced-learn 0.12.4. Report generated 2026-10-10 06:40 IST by reports/generate.py 1.0 (from Jonathan's render_report.py 0.1).

> ## 🟢 VERIFIED
>
> **Recommended action:** Approve  
> **Confidence:** High. All required checks and evals passed, 3 runs per side gave identical results (stability old 1.0, new 1.0), 3 of 3 golden cases hold, tests ran without network.
>
> Scope: this run compares two released versions, not a single PR's commits. Any change between the two versions can cause what is shown here.

## Summary in plain English

- **What it says it does:** not available (no PR or release description was supplied with this run).
- **What we observed:** No test of imbalanced-learn 0.12.4 changed result between scikit-learn 1.5.1 and 1.5.2 (2277 tests, 3 runs per side).
- **What you should do:** Approve.

## Claims vs reality

Claims: not available (no PR or release description supplied). No behavior change was observed, so there is nothing unmentioned to flag.

## What changed in behavior

No behavior change: no test went from passing to failing, and every test module still loads.

## What went right

| Status | Check | Detail |
|---|---|---|
| 🟢 **pass** | Correct versions installed | old scikit-learn==1.5.1, new scikit-learn==1.5.2, imbalanced-learn==0.12.4 on both sides (freeze + import probe) |
| 🟢 **pass** | Only the upstream version differs between sides | freeze diff: ['scikit-learn==1.5.1', 'scikit-learn==1.5.2'] |
| 🟢 **pass** | Isolated environments | both venvs created by uv without system site-packages (checked sys.prefix and sys.path) |
| 🟢 **pass** | Thread count pinned to 1 | OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS, NUMEXPR_NUM_THREADS, VECLIB_MAXIMUM_THREADS, BLIS_NUM_THREADS = 1 in both envs |
| 🟢 **pass** | All runs completed | 3 runs per side requested (minimum 3); JUnit XML present and no suite timeout on every run |
| 🟢 **pass** | Old side healthy (baseline is trustworthy) | dependent imports on old: {'imblearn': 'ok'}; old side passed [2243, 2243, 2243] tests with collection errors [0, 0, 0] |
| 🟢 **pass** | Repeatable results | share of tests with the same outcome in every run: old 1.0, new 1.0 (advisory threshold 0.99) |
| 🟢 **pass** | No secrets in logs | scrubbed env; no credential-like strings found in logs |
| 🟢 **pass** | Record format valid | record matches harness/schema/observation.schema.json |
| 🟢 **pass** | Runs per side | 3 (minimum 3), alternating old and new |
| 🟢 **pass** | Guardrails respected | tests ran with no network; nothing was posted or filed by the runner |
| 🟢 **pass** | Matches the prediction written before the run | no break: 1.5.2 is a bug-fix release; imbalanced-learn 0.12.4 was the current release for the 1.5 series |
| 🟢 **pass** | Nathan's evals | 6 of 7 eval checks passed (see 'Evals and guardrails') |

## What went wrong and how to fix it

### Issues in the PR or release

None found.

### Issues in our test environment

None found.

## Trust checks

| Check | Status | Detail |
|---|---|---|
| Required checks (gates) | 🟢 **7 of 7 passed** | all passed |
| Advisory checks | 🟢 **2 of 2 passed** | all passed |
| Evals (Nathan) | 🟢 **APPROVE** | no failures or warnings |
| Golden cases (stored records) | 🟢 **3 of 3 hold** | checked against the stored golden records (harness 1.0) with the eval gate's code, not re-run for this report. This run is itself one of the golden cases, so this check is partly circular for it |
| Golden cases (re-run) | ⚪ **not available** | no golden re-run recorded in this record (golden_check) |
| Known-answer replay (fresh re-run) | 🟢 **all passed** | replayed 2026-10-10 06:30:21 IST, harness 1.0 |
| Report citations | ⚪ **skip** | no claim rows in this report |
| Flaky rate | 🟢 **0 of 2277 (0.0%)** | stability old 1.0, new 1.0 |
| Network during tests | 🟢 **off** | install: allowed (uv from PyPI/nightly index, git clone of the tag); tests: no network (unshare -rn, private network namespace) |
| Threads | 🟢 **pinned to 1** | OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, BLIS_NUM_THREADS=1 |
| Machine | 🔵 **box** | Intel(R) Xeon(R) Processor, 8 CPUs, 15.6 GB RAM, Linux x86_64, CI: not available |
| Report matches the record | 🟢 **consistent** | break and import-failure counts recomputed from class-*.txt and JUnit equal the record |
| Prediction before the run | 🟢 **yes** | no break: 1.5.2 is a bug-fix release; imbalanced-learn 0.12.4 was the current release for the 1.5 series |

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
| versions_installed | 🟢 **pass** | scikit-learn 1.5.1 -> 1.5.2; env differs only in scikit-learn | - |
| runs_per_side | 🟢 **pass** | 3 alternating runs per side, identical counts within each side | - |
| single_thread | 🟢 **pass** | OMP/OPENBLAS/MKL_NUM_THREADS=1 | - |
| matches_expected | 🟢 **pass** | outcome matches the prediction written before the run (no_break) | - |
| golden:golden-clean-sklearn151-152-imblearn | 🟢 **pass** | golden-clean-sklearn151-152-imblearn: all expected values hold | - |
| llm_citations | ⚪ **skip** | no Nemotron explanations in this record yet | - |
| report_citations | ⚪ **skip** | no claim rows in this report | - |

## Reviewer checklist

- [ ] I read the verdict, the recommended action and the confidence.
- [ ] I checked the claims vs reality table for any 'false' or 'unmentioned change' rows, and opened at least one cited log line.
- [ ] I confirmed there are no behavior changes.
- [ ] I confirmed the required checks and Nathan's evals passed (Trust checks, Evals and guardrails).
- [ ] I am satisfied the environment issues (if any) do not change the decision.

**Decision:** ☐ Approve ☐ Approve with notes ☐ Reject ☐ Re-run    Reviewer: ________  Date: ________

## Rerun command

From the blast-radius repo root. The wrapper forces 3 alternating runs per side and the single-thread env, records machine_type, writes under ./data and never posts anything:

```
BR_RUNNER=/workspace/blast-radius-research/harness/br_run.py python -m harness.run \
  --upstream scikit-learn \
  --old 1.5.1 \
  --new 1.5.2 \
  --dependent imbalanced-learn \
  --dep-version 0.12.4 \
  --tests wheel:imblearn \
  --extra-pkgs 'numpy==2.1.3 scipy==1.14.1 pandas==2.2.3' \
  --cpus 4-7 \
  --python 3.12 \
  --expected 'no break: 1.5.2 is a bug-fix release; imbalanced-learn 0.12.4 was the current release for the 1.5 series' \
  --expected-class no_break \
  --id golden-clean-sklearn151to152-imblearn0124-rerun
```

Needs Linux x86_64, uv 0.12 or newer, git and unshare.

## Evidence links

| What | Link (relative to this report) |
|---|---|
| pytest summary, old side run 1 | [pytest-old-1.log:123](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/pytest-old-1.log) «2238 passed, 33 skipped, 1 xfailed, 5 xpassed, 62 warnings in 45.39s» |
| pytest summary, new side run 1 | [pytest-new-1.log:123](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/pytest-new-1.log) «2238 passed, 33 skipped, 1 xfailed, 5 xpassed, 62 warnings in 44.26s» |
| Full record | [record.json](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/record.json) |
| Run arguments | [args.json](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/args.json) |
| Setup log | [setup.log](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/setup.log) |
| Installed packages, old | [freeze-old.txt](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/freeze-old.txt) |
| Installed packages, new | [freeze-new.txt](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/freeze-new.txt) |
| Package difference | [freeze-diff.txt](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/freeze-diff.txt) |
| pytest logs | [pytest-new-1.log](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/pytest-new-1.log), [pytest-new-2.log](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/pytest-new-2.log), [pytest-new-3.log](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/pytest-new-3.log), [pytest-old-1.log](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/pytest-old-1.log), [pytest-old-2.log](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/pytest-old-2.log), [pytest-old-3.log](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/pytest-old-3.log) |
| JUnit XML | [junit-new-1.xml](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/junit-new-1.xml), [junit-new-2.xml](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/junit-new-2.xml), [junit-new-3.xml](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/junit-new-3.xml), [junit-old-1.xml](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/junit-old-1.xml), [junit-old-2.xml](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/junit-old-2.xml), [junit-old-3.xml](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/junit-old-3.xml) |
| Test lists per class | [class-already_broken.txt](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/class-already_broken.txt), [class-fixed_by_new.txt](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/class-fixed_by_new.txt), [class-flaky.txt](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/class-flaky.txt), [class-import_failure.txt](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/class-import_failure.txt), [class-lost_tests.txt](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/class-lost_tests.txt), [class-real_break.txt](../../../../../blast-radius-research/research/runs/golden-clean-sklearn151to152-imblearn0124/class-real_break.txt) |

## Appendix

### Commits and versions

| Item | Value |
|---|---|
| PR | not available |
| PR base / head / merge commit | not available |
| Upstream | scikit-learn: old 1.5.1, new 1.5.2 (requested 1.5.2) |
| Upstream commits (old / new) | PyPI release wheels (no commit recorded) |
| Dependent | imbalanced-learn 0.12.4 |
| Tests from | wheel (tests shipped in the installed package: imblearn); selection: imblearn |
| Python | 3.12.15 |
| Environment difference | scikit-learn==1.5.1, scikit-learn==1.5.2 |
| Runner | harness 1.0, 4 workers, import mode prepend, per-test timeout 300 s, memory cap 6.0 GB |
| Record schema | v1; written against rev 1 (sha256 5a3c3d36b773...); valid under current rev 2 (additive) |
| Run by | Jonathan on box, 2026-10-10 05:36 IST |
| Hand check | not available |
| Upstream issue | not available |
| Per-test outcomes | not available |
| AI explanation | not yet wired |

### Timings

Total wall time 258.2 s; mean test time old 40.5 s, new 43.6 s.

| Side | Run | Exit | Seconds | pytest summary |
|---|---|---|---|---|
| old | 1 | 0 | 46.05 | 2238 passed, 33 skipped, 1 xfailed, 5 xpassed, 62 warnings in 45.39s |
| new | 1 | 0 | 45.04 | 2238 passed, 33 skipped, 1 xfailed, 5 xpassed, 62 warnings in 44.26s |
| old | 2 | 0 | 41.66 | 2238 passed, 33 skipped, 1 xfailed, 5 xpassed, 62 warnings in 40.94s |
| new | 2 | 0 | 42.44 | 2238 passed, 33 skipped, 1 xfailed, 5 xpassed, 62 warnings in 41.57s |
| old | 3 | 0 | 33.83 | 2238 passed, 33 skipped, 1 xfailed, 5 xpassed, 62 warnings in 33.13s |
| new | 3 | 0 | 43.43 | 2238 passed, 33 skipped, 1 xfailed, 5 xpassed, 62 warnings in 42.61s |

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
