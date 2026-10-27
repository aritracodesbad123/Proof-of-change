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
- If main's checkpoint fails, that failure is reported first, the same as in serial order, and the check does not wait for the PR build. The PR build is marked abandoned in the record (`contree.pr_build`); it ends on Contree's own time limit and its image is never used.
- A probe-planning error is raised as itself. The background checkpoint build is still waited for, but its result never replaces the planning error.
- Probe planning never writes `rec['contree']`, which the background build owns.
- One code path: the serial and parallel checks share `_contree_only_pair`; only the prep step and the timed-run schedule differ.
- If one side has no test targets, the other side runs alone, the same as in serial order.

## Fallback to the flag-off build
The flag never changes a verdict. Because the PR side is normally built from the base image instead of on main's image, a dependency with an unpinned range could resolve differently. So after both builds the installed packages on each side are compared (`pip list`, editable installs of the project left out). The PR side is rebuilt on top of main's image, exactly as with the flag off, when:
- any installed version differs between the sides, or
- a side's package list cannot be read.

When the pull request changes a dependency file (pyproject, setup, requirements, constraints or a lock file), the parallel build is skipped and both sides are built exactly as with the flag off. Each fallback is recorded as `contree.parallel_fallback` with its reason. Main's Python check and the PR-own-code check run after every build path, parallel or fallback.

Blocked checks plan and freeze the probes before returning, so their records match the flag-off records.

## Timings
Running the pairs at the same time means the two sides compete for the same service at once. Per-side seconds from parallel mode are recorded for completeness only and must not be used in any speed claim. Only whole-check wall time, measured with the flag on and off on the same cases, may be compared.

## Risk
The flag stays off until the on/off comparison shows matching verdicts.
