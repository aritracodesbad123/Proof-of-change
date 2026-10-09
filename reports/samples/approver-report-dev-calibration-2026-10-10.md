# Blast Radius approver report

Generated 2026-10-10 05:21 IST from `/workspace/blast-radius-research/research/dev-runs/observations-dev.jsonl`. Evaluated on: box, x86_64, Linux, 8 cpus.
Schema mode: strict (machine_type required).

## Recommendation: **REJECT**

Check totals: fail 2, pass 10, skip 2, todo 1, warn 2

| Run | Recommendation | Fail | Warn |
|---|---|---|---|
| cal-pandas300rc0-upsetplot090 | REJECT | 1 | 1 |
| cal-sklearn160rc1-imblearn0124 | REJECT | 1 | 1 |

## Golden eval coverage

- PASS golden-sklearn160rc1-imblearn-import-failure: covered by ['cal-sklearn160rc1-imblearn0124']
- PASS golden-pandas300rc0-upsetplot-cow: covered by ['cal-pandas300rc0-upsetplot090']
- TODO golden-clean-pair-zero-breaks: no record in this batch for golden-clean-pair-zero-breaks (TODO: Jonathan to choose the clean (upstream old/new, dependent) pair. The match below is a placeholder that matches nothing until he does.)

## cal-pandas300rc0-upsetplot090: REJECT

- **Pair:** pandas 2.3.3 -> 3.0.0rc0 vs UpSetPlot 0.9.0
- **Run by:** Jonathan (box) on 2026-10-10 05:17 IST; Python 3.13.5
- **Machine type:** NOT RECORDED (legacy field machine='box', host='grok-bot-vm-345453355', cpus=8)
- **Tests:** repo tag 0.9.0 (https://github.com/jnothman/UpSetPlot, commit 7d889a9df7974509965a5ffd313e27764d43322a) [upsetplot/tests]
- **Prediction (written before the run):** break: Copy-on-Write makes chained assignment in plotting.py a no-op (UpSetPlot issue #303) -> matches: yes

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

- versions_installed: pandas 2.3.3 -> 3.0.0rc0; env differs only in pandas
- runs_per_side: 3 alternating runs per side, identical counts within each side
- matches_expected: outcome matches the prediction written before the run (break)
- golden:golden-pandas300rc0-upsetplot-cow: golden-pandas300rc0-upsetplot-cow [TODO data]: all expected values hold

### What went wrong

- **FAIL** schema: cal-pandas300rc0-upsetplot090: missing field 'machine_type'; cal-pandas300rc0-upsetplot090: missing field 'thread_env'
- **WARN** single_thread: thread_env not recorded (br_run.py sets OMP/OPENBLAS/MKL=1 internally but does not record it)

### How to fix

- schema: Run through `python -m harness.run` so machine_type/thread_env are added, or fix the runner output.
- single_thread: Run through `python -m harness.run`, which records thread_env.

### Not checked / pending

- SKIP llm_citations: no Nemotron explanations in this record yet

## cal-sklearn160rc1-imblearn0124: REJECT

- **Pair:** scikit-learn 1.5.2 -> 1.6.0rc1 vs imbalanced-learn 0.12.4
- **Run by:** Jonathan (box) on 2026-10-10 05:17 IST; Python 3.13.5
- **Machine type:** NOT RECORDED (legacy field machine='box', host='grok-bot-vm-345453355', cpus=8)
- **Tests:** wheel (installed package, imblearn) [imblearn]
- **Prediction (written before the run):** break: imblearn 0.12.4 imports sklearn.utils._tags._safe_tags, removed in 1.6 (known from the first reproduction) -> matches: yes

| real_break | import_failure | already_broken | flaky | fixed_by_new | lost_tests |
|---|---|---|---|---|---|
| 280 | 13 | 0 | 0 | 0 | 1713 |

Top break signatures:

- `AttributeError: 'ValueDifferenceMetric' object has no attribute '_validate_data'. Did you mean: '_validate_params'?` x131
- `AttributeError: 'RandomOverSampler' object has no attribute '_check_n_features'` x28
- `AttributeError: 'RandomUnderSampler' object has no attribute '_check_n_features'` x19
- `AttributeError: 'KMeansSMOTE' object has no attribute '_validate_data'. Did you mean: '_validate_params'?` x13
- `collection failure` x13

### What went right

- versions_installed: scikit-learn 1.5.2 -> 1.6.0rc1; env differs only in scikit-learn
- runs_per_side: 3 alternating runs per side, identical counts within each side
- matches_expected: outcome matches the prediction written before the run (break)
- golden:golden-sklearn160rc1-imblearn-import-failure: golden-sklearn160rc1-imblearn-import-failure [TODO data]: all expected values hold

### What went wrong

- **FAIL** schema: cal-sklearn160rc1-imblearn0124: missing field 'machine_type'; cal-sklearn160rc1-imblearn0124: missing field 'thread_env'
- **WARN** single_thread: thread_env not recorded (br_run.py sets OMP/OPENBLAS/MKL=1 internally but does not record it)

### How to fix

- schema: Run through `python -m harness.run` so machine_type/thread_env are added, or fix the runner output.
- single_thread: Run through `python -m harness.run`, which records thread_env.

### Not checked / pending

- SKIP llm_citations: no Nemotron explanations in this record yet

---
Rule: any FAIL means REJECT. WARN and TODO items are listed for the approver but do not block. Blast Radius never files or posts anything; a person decides what to send upstream.
