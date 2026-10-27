# Test isolation for random test order

Status: proposed

## Decision
Three tests depended on what earlier tests left behind. Each now isolates the shared state itself; no assertion was relaxed.

1. **`test_step_timings_recorded_and_shown`** faked the clock by patching `time.time` for the whole process with a 4-value list. A console job's worker thread (from the playback test) sets `POC_PROGRESS_PATH` in `os.environ` for the whole process and never removes it. When that test ran first, every `run_progress.emit` also wrote a progress event, which read the clock again, so the list ran out (`StopIteration`). Fix: the test replaces only `run_progress`'s clock and clears `POC_PROGRESS_PATH` for itself.
2. **`test_list_runs_reads_record`** read `console_api._recent_runs`, the in-memory list of remembered runs, which other tests (`remember_run`, playback jobs) fill and never empty. Fix: an autouse fixture gives every test an empty `_recent_runs` and puts back `POC_PROGRESS_PATH` after each test, even if a worker thread changed it.
3. **The sandbox `listener` fixture** closed its socket while its accept thread was still blocked, so the thread raised `OSError` in whichever test happened to be running (an unhandled thread exception). Fix: the thread stops on `OSError`, and teardown shuts the socket down, closes it and joins the thread.

## Boundaries
Tests only. No product code changes. The worker thread setting `POC_PROGRESS_PATH` process-wide is left as it is and noted as a follow-up.

## Evidence
12 random-order full-suite runs (seeds 11, 22, 33, 44, 55, 1-7) with unhandled thread exceptions treated as errors and keys unset: all passed.
