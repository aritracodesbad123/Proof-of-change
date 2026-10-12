# Benchmark mode and probe adequacy

## Benchmark mode (`ops/bench.py`)

Runs the normal per-PR pipeline on PRs that were merged long ago and whose outcome is known.

```
python3 ops/daily_run.py --bench bench/benchmark-v0.csv --ids B01,B14 [--bench-out runs/bench-v0]
```

- Main side = the first parent of the merge commit; PR side = the merge commit (what actually landed). Both are
  fetched by SHA. If the merge commit's first parent is not the main SHA in the inputs file, the case is refused.
- Each case then takes the source-pair route: both sides installed from the checkout, mapped tests 3 times per
  side, coverage gate, probes, verdict.
- Output: one result JSON per case and baseline, `runs/bench-v0/<ID>-<baseline>.json` (the full record plus a
  `bench` block and `case_id`). Logs go to `runs/bench-v0/logs/<ID>-<baseline>/`.
- `bench/benchmark-v0.csv` is a copy of the v0 inputs (19 cases). Any inputs file with the same columns works.
- Answer keys are never read. Any file whose name contains `answers` is refused (symlinks too), and so is an
  inputs file that has answer-key columns. Scoring is a separate step (`evals/score_bench.py`).

## Probe adequacy (`poc/probe_adequacy.py`)

After the timed probe runs, each probe runs once more on the main (old) side under coverage.py. Its entry gains
`probe_changed_line_coverage` (changed lines it executed out of the changed executable lines, plus an adequacy
value), and the record gains a summary under the same name.

- **adequate**: it ran at least one changed line, so it decides as before.
- **not_adequate**: it ran none. It can never lead to `verified`: its matching ("same", "proven") results are
  dropped and it does not count as checking a behaviour claim. Differences it finds are still flagged.
- **unmeasured**: coverage could not be measured (for example with `--no-coverage`). It decides as before, and the
  report says so.

On the main side, "changed lines" means the lines the change replaces or deletes. For pure insertions, the lines
on either side of the insertion point stand in. A file that is new on the PR side has no main-side lines.
