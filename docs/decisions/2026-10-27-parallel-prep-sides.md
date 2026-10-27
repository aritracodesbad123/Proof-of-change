# Parallel Contree prep and sides (POC_PARALLEL)

Status: proposed

## Decision
A product check run with `POC_PARALLEL=1` saves wall time in three places. The flag is off by default until the on/off comparison is reviewed.

1. **Prep during probe writing.** The Contree checkpoint install starts in a background thread while the model writes and freezes the probes. Probe planning reads only local files and the model, never a sandbox. The PR checkpoint install runs only the project's own install, never a probe, and `pr_side_started_at` is set after both finish. So "probes are frozen before PR-side execution" still holds.
2. **Separate sandboxes for main and PR.** Both checkpoints are built at the same time from the base image. With the flag off, the PR checkpoint is still forked from main's.
3. **Timed runs in pairs.** For each of the 3 timed runs, the main and PR pytest start together in their own disposable sandboxes. Records are written in the same order as the serial schedule.

## Boundaries
- Only product checks use it (`product_route`). The study route and its output are unchanged, and so are the verdict rules.
- Pull-request code still runs only in Contree.
- If main's checkpoint fails, that failure is reported first, the same as in serial order.
- If one side has no test targets, the other side runs alone, the same as in serial order.

## Risk
Because the PR side is no longer forked from main, a dependency with an unpinned range could resolve to a different version on each side. Running the pairs at the same time also means the two sides compete for the same service at once. Per-side seconds are still measured per run. The flag stays off until the 3-case comparison shows matching verdicts.
