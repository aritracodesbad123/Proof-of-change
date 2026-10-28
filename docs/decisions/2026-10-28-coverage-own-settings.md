# Coverage gate measures with its own coverage settings

Status: proposed

## Problem
The coverage gate re-runs the PR's tests under pytest-cov with `--cov=<changed folder>`, which is a coverage
`source`. When a project's own coverage config sets `include` (pytest-dev/pytest#15256 does), coverage warns
"--include is ignored because --source is set". That project's pytest config has `filterwarnings = error`, so the
warning became an error at startup. Coverage then recorded nothing, and the check could not be marked verified.

## Decision
- The measurement uses a small coverage settings file of our own, passed with `--cov-config` on both the local and
  Contree routes. Coverage then reads only that file, so the project's `include`/`omit` can no longer conflict with
  our source. This fixes the root cause.
- The same file turns off coverage's own setup warnings (`disable_warnings`: include-ignored, no-data-collected,
  module-not-measured and similar). This is done inside coverage. No `-W` flag is added, and the project's
  `filterwarnings` are unchanged, so the project's own warnings are still errors for its code.
- The coverage log starts with a plain "Coverage setup:" line saying so.
- Nothing is per repository.

## Effect on verdicts
This only lets the measurement run. A measured coverage result can confirm or hold back a verdict through the
existing coverage gate, but this change adds no way to raise one.
