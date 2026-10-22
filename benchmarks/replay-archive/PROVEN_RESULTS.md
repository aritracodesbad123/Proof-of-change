# Earlier results (before code version 0fa0016)

This section was on the main README before the 30-PR batch on 0fa0016 replaced it. Paths below are relative to the repository root.

## Proven results (archived)

Each result below was reproduced 3 times on each side, with the same outcome every time. These are replays run after
the releases happened, to show the break was already visible at the release candidate. The records are in
`evals/fixtures/golden_v1.jsonl` and the reports in `reports/samples/golden-v1/`. The full raw logs are too large for
the repo; excerpts are in `evals/fixtures/runs/`.

**A real scikit-learn break, visible 24 days before the release**
scikit-learn 1.6.0rc1 (published 15 Nov 2024) no longer had a private helper, `_safe_tags`, that imbalanced-learn
0.12.4 imported. It was removed in [scikit-learn#29677](https://github.com/scikit-learn/scikit-learn/pull/29677).

| | scikit-learn 1.5.2 | scikit-learn 1.6.0rc1 |
|---|---|---|
| imbalanced-learn 0.12.4 tests | 2,238 passed | 0 passed, 525 errors (import fails: `_safe_tags`) |

Verdict: NEEDS ATTENTION. The final 1.6.0 came out on 9 Dec 2024, 24 days after the release candidate (it brought
`_safe_tags` back as a deprecated helper, [scikit-learn#30327](https://github.com/scikit-learn/scikit-learn/pull/30327)).

**A real pandas 3.0 break, visible 49 days before the release**
pandas 3.0.0rc0 (published 3 Dec 2025) makes Copy-on-Write the default
([pandas#56633](https://github.com/pandas-dev/pandas/pull/56633)), which breaks UpSetPlot 0.9.0 plotting
([UpSetPlot#303](https://github.com/jnothman/UpSetPlot/issues/303), opened 25 Jan 2026).

| | pandas 2.3.3 | pandas 3.0.0rc0 |
|---|---|---|
| UpSetPlot 0.9.0 tests | 233 passed, 6 failed | 166 passed, 73 failed |

Verdict: NEEDS ATTENTION. 67 new failures, 36 of them `Invalid RGBA argument: nan`. The 6 tests that failed on both
sides were labelled as already broken, not blamed on the change. The final 3.0.0 came out on 21 Jan 2026, 49 days
after the release candidate.

**No false alarm on a safe upgrade**
scikit-learn 1.5.1 to 1.5.2, tested against imbalanced-learn 0.12.4: 2,238 passed on both sides in every run.
Verdict: VERIFIED.

**Being honest about what tests can't see**
In our first open-PR study, one PR ([mlxtend#1229](https://github.com/rasbt/mlxtend/pull/1229)) changed results for
some inputs under a fixed random seed, and every existing test still passed, so the check said VERIFIED. An
independent re-check found the change. Running the project's tests alone can miss that kind of change. When a Nebius
API key is set, Proof-of-Change also runs *claim probes* (small scripts written from what the PR says it does) so
those gaps are easier to catch. We still report misses like the early study openly.
