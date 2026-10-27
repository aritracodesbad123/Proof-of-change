# Progress path is passed per check, not set process-wide

## Context
The console check worker set `POC_PROGRESS_PATH` in the process environment and never restored it.
After any check (including the vetted-sample playback) every later `run_progress.emit` in the same
process wrote to that check's file, and concurrent checks overwrote each other's value.

## Decision
- `run_progress.emit` takes an optional `path`. When given, it is used instead of the environment.
- The console worker (and the `queued` event) pass the check's own progress file explicitly and no
  longer write `POC_PROGRESS_PATH` to `os.environ`.
- The child check process still receives `POC_PROGRESS_PATH` through its own copied environment,
  so emits inside the child are unchanged.

## Evidence
- New test `test_playback_leaves_the_progress_variable_unchanged` (unset and preset cases) fails on
  the old code and passes now; the check's own progress still ends at `done`.
- Full suite in random order, several seeds, with unhandled thread exceptions as errors; ruff clean.
