# The results page shows only the current batch

**Date:** 2026-10-22
**Status:** proposed

## What changed

- `ops/export_replay.py` has a new `--no-curated` flag. With it, the page catalog holds only the runs passed with `--runs`.
- The results page and the README scoring section show only the 30-PR random batch on code version `0fa0016`. The earlier page checks are kept unchanged in `benchmarks/replay-archive/`.
- Scoring counts catches, misses and false alarms only where there is outside proof: a later revert, a follow-up bug report, or a maintainer's explicit confirmation. Passing maintainer CI is not proof. PRs without proof are listed as unlabelled.

## Why

Mixing runs from older code versions with current results made the page hard to read and the numbers hard to trust.

## Decision

1. The page shows one batch, labelled with its code version.
2. Older runs stay in the repository, labelled by version.
3. No accuracy-type rate is published without outside proof.
