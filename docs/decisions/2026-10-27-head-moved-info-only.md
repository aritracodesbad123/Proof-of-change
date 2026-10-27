# A moved PR head is information only in the benchmark

Status: proposed

## Context
Benchmark cases pin a base and head commit. The check clones and diffs exactly those commits, so a PR whose live head has moved since the case was written is still checked accurately.

## Decision
- `bench/run.py` keeps `head_moved` and `current_head_sha` in each result for information only.
- A case is reported `not_run` only when the commits the check actually tested (base, head, PR side) differ from the case file.

## Consequences
Cases keep running as upstream PRs move on, and drift in the tested commits is still refused.
This replaces the "moved head is reported not run" rule in the pinned-commits decision note.
