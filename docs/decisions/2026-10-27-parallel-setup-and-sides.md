# Product checks overlap setup with probe planning and run both sides together

## What changed

Two speed changes, both for product checks on Contree only:

1. Contree setup (the two checkpoints, the Python check and the installs) now starts in a background
   thread while the model writes and freezes the probes. The check waits for both before any test or
   probe runs.
2. For the test runs and the probe runs, run N on main and run N on the pull request now go at the same
   time. The runs themselves still go one after another (1, 2, 3).

## What did not change

- Each side still runs in its own checkpoint. Nothing is shared between main and the pull request.
- Every Contree call still waits for a slot under the existing limit on Contree calls at once.
- Results are recorded main first, then the pull request, in run order, exactly as before. The saved
  junit files, logs and probe outputs have the same names and contents.
- Probes are still written and frozen before any probe or test runs on the pull request side. The
  freeze check still runs before each pull request probe run starts.
- Errors come out the same way. A setup failure gives the same refusal text. If planning fails, its
  error is raised first, as it would have been when planning ran first, after setup has finished. A
  Contree error on either side stops the run with that error.
- Verdict rules are untouched.

## Switching it off

`POC_PARALLEL_SIDES=0` or `--no-parallel-sides` puts a product check back on the earlier order. A study
run and the daily study never use it, so their output is byte-identical to before.

## Timings

A product check records start, end and seconds for setup, probe planning, tests and probes under
`parallel_sides.steps`, with `parallel_sides.enabled` saying which order was used. Nothing reads these
for a verdict.
