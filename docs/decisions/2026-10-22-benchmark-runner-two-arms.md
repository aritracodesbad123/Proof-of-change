# Benchmark runner with a tests-only arm and a tests+probes arm

**Status:** proposed

## What changed

A new `bench` package adds three parts. `bench/manifest.py` defines and checks the case file format, which
is documented in `docs/benchmark-manifest.md`. `bench/run.py` runs every case through the product check in
Contree, once per arm. `bench/summarize.py` turns the results into counts and rates.

The two arms use the same pull request, commits, sandbox and timeouts. Only what decides the verdict differs.
The tests-only arm compares the project's tests with no model calls. The tests+probes arm adds model-written
probes from the live provider. An optional third arm also turns on the advisory swarm.

## Why

The question is whether the probes catch regressions that ordinary tests miss. Answering it needs the same
cases run with and without probes, with the misses counted honestly.

## Rules

- Runs go only through `--product-check --sandbox-backend contree` with `POC_REQUIRE_CONTREE=1`. There is no
  local fallback, and nothing is posted anywhere.
- A case with no record, or one that tested commits other than the case file's, is not run. Not run and
  could_not_verify count as misses, never as catches or wins.
- The runner refuses fixture cases. The unit tests use three fixture cases that are marked as fixtures.
- Verdict rules, the study path and the daily study are unchanged. The runner only reads the check's record.
  The stage states are derived from that record and are not new record fields.
- No significance claims. Every rate is shown with its count and n.

## Limits

- An open PR's base branch can move. When it does, the check tests a newer base than the case file names, and
  the case is not run. Case files for open PRs need refreshing before a run.
- Model calls and cost come from the record's `cost` block. Swarm calls are listed apart there and are not
  added to the arm's totals.
- The install stage state is read from the installed-commit check and the reason text. When neither says,
  it is `unknown`, not `ok`.
