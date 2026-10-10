# Blast Radius approver report

Generated 2026-10-10 05:48 IST from `evals/fixtures/golden_v1.jsonl`. Evaluated on: box, x86_64, Linux, 8 cpus.
Schema mode: strict v1 (full shared schema harness/schema/observation.schema.json).

## Recommendation: **APPROVE**

Check totals: pass 22, skip 3

| Run | Recommendation | Fail | Warn |
|---|---|---|---|
| golden-sklearn160rc1-imblearn0124 | APPROVE | 0 | 0 |
| golden-pandas300rc0-upsetplot090 | APPROVE | 0 | 0 |
| golden-clean-sklearn151to152-imblearn0124 | APPROVE | 0 | 0 |

## Golden eval coverage

- PASS golden-sklearn160rc1-imblearn-import-failure: covered by ['golden-sklearn160rc1-imblearn0124']
- PASS golden-pandas300rc0-upsetplot-cow: covered by ['golden-pandas300rc0-upsetplot090']
- PASS golden-clean-sklearn151-152-imblearn: covered by ['golden-clean-sklearn151to152-imblearn0124']

## golden-sklearn160rc1-imblearn0124: APPROVE

- **Pair:** scikit-learn 1.5.2 -> 1.6.0rc1 vs imbalanced-learn 0.12.4
- **Run by:** Jonathan on 2026-10-10 05:36 IST; Python 3.13.5
- **Machine type:** box, x86_64, Linux, 8 cpus
- **Tests:** wheel (tests shipped in the installed package: imblearn) [imblearn]
- **Prediction (written before the run):** break: imbalanced-learn 0.12.4 cannot be imported on 1.6.0rc1 (ImportError on sklearn.utils._tags._safe_tags). Expect old 2238 passed (pytest summary), new 0 passed / 525 errors, import_failure 46 modules, lost_tests 2243, real_break 0. -> matches: yes

| real_break | import_failure | already_broken | flaky | fixed_by_new | lost_tests |
|---|---|---|---|---|---|
| 0 | 46 | 0 | 0 | 0 | 2243 |

Top break signatures:

- `E   ImportError: cannot import name '_safe_tags' from 'sklearn.utils._tags' (<path>` x505
- `package import imblearn: ImportError: cannot import name '_safe_tags' from 'sklearn.utils._tags' (<path>` x46
- `ImportError: cannot import name '_safe_tags' from 'sklearn.utils._tags' (<path>` x19
- `ImportError: cannot import name 'assert_no_warnings' from 'sklearn.utils._testing' (<path>` x1

### What went right

- schema: record matches the shared schema blast-radius/observation/v1, mode v1 (schema reference verified by sha256)
- versions_installed: scikit-learn 1.5.2 -> 1.6.0rc1; env differs only in scikit-learn
- runs_per_side: 3 alternating runs per side, identical counts within each side
- single_thread: OMP/OPENBLAS/MKL_NUM_THREADS=1
- matches_expected: outcome matches the prediction written before the run (break)
- golden:golden-sklearn160rc1-imblearn-import-failure: golden-sklearn160rc1-imblearn-import-failure: all expected values hold
- golden:golden-sklearn160rc1-imblearn-import-failure:import_message: import error mentioning '_safe_tags' found in new-side import probe (imblearn: ImportError: cannot import name '_safe_tags' from 'sklearn.utils._tags' (/worksp); break signature (ImportError: cannot import name '_safe_tags' from 'sklearn.utils._tags' (<path>)

### What went wrong

- nothing

### How to fix

- no action needed

### Not checked / pending

- SKIP llm_citations: no Nemotron explanations in this record yet

## golden-pandas300rc0-upsetplot090: APPROVE

- **Pair:** pandas 2.3.3 -> 3.0.0rc0 vs UpSetPlot 0.9.0
- **Run by:** Jonathan on 2026-10-10 05:36 IST; Python 3.13.5
- **Machine type:** box, x86_64, Linux, 8 cpus
- **Tests:** repo tag 0.9.0 (https://github.com/jnothman/UpSetPlot, commit 7d889a9df7974509965a5ffd313e27764d43322a) [upsetplot/tests]
- **Prediction (written before the run):** break: 67 real breaks from Copy-on-Write (Invalid RGBA argument: nan) and 6 already broken (pytest.warns(None)) -> matches: yes

| real_break | import_failure | already_broken | flaky | fixed_by_new | lost_tests |
|---|---|---|---|---|---|
| 67 | 0 | 6 | 0 | 0 | 0 |

Top break signatures:

- `ValueError: Invalid RGBA argument: nan` x36
- `AssertionError: DataFrame.index level [N] are different` x16
- `ValueError: Do not know how to convert N    NaN` x13
- `ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N     #0000002e` x1
- `ValueError: 'c' argument must be a color, a sequence of colors, or a sequence of numbers, not N           NaN` x1

### What went right

- schema: record matches the shared schema blast-radius/observation/v1, mode v1 (schema reference verified by sha256)
- versions_installed: pandas 2.3.3 -> 3.0.0rc0; env differs only in pandas
- runs_per_side: 3 alternating runs per side, identical counts within each side
- single_thread: OMP/OPENBLAS/MKL_NUM_THREADS=1
- matches_expected: outcome matches the prediction written before the run (break)
- golden:golden-pandas300rc0-upsetplot-cow: golden-pandas300rc0-upsetplot-cow: all expected values hold

### What went wrong

- nothing

### How to fix

- no action needed

### Not checked / pending

- SKIP llm_citations: no Nemotron explanations in this record yet

## golden-clean-sklearn151to152-imblearn0124: APPROVE

- **Pair:** scikit-learn 1.5.1 -> 1.5.2 vs imbalanced-learn 0.12.4
- **Run by:** Jonathan on 2026-10-10 05:36 IST; Python 3.12.15
- **Machine type:** box, x86_64, Linux, 8 cpus
- **Tests:** wheel (tests shipped in the installed package: imblearn) [imblearn]
- **Prediction (written before the run):** no break: 1.5.2 is a bug-fix release; imbalanced-learn 0.12.4 was the current release for the 1.5 series -> matches: yes

| real_break | import_failure | already_broken | flaky | fixed_by_new | lost_tests |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 |

### What went right

- schema: record matches the shared schema blast-radius/observation/v1, mode v1 (schema reference verified by sha256)
- versions_installed: scikit-learn 1.5.1 -> 1.5.2; env differs only in scikit-learn
- runs_per_side: 3 alternating runs per side, identical counts within each side
- single_thread: OMP/OPENBLAS/MKL_NUM_THREADS=1
- matches_expected: outcome matches the prediction written before the run (no_break)
- golden:golden-clean-sklearn151-152-imblearn: golden-clean-sklearn151-152-imblearn: all expected values hold

### What went wrong

- nothing

### How to fix

- no action needed

### Not checked / pending

- SKIP llm_citations: no Nemotron explanations in this record yet

---
Rule: any FAIL means REJECT. WARN and TODO items are listed for the approver but do not block. Blast Radius never files or posts anything; a person decides what to send upstream.
