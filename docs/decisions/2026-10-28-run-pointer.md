# Every run is findable under ops/runs/<date>/

A check started with another `--ops-dir`, or with a `--date` name that is not a date, wrote its run folder somewhere the monitor and the daily check do not look, so its results were missed.

Now, right after the run folder is created, a run outside `ops/runs/<YYYY-MM-DD>...` appends one line, `{"run_dir", "started_ist"}`, to `ops/runs/<YYYY-MM-DD>/RUN_POINTERS.jsonl` (the start date in IST). Dated runs already in `ops/runs/` leave nothing. The line is written once per run folder, and a failure to write it only prints a warning; it never fails the run. `ops/runs/` stays out of git. Tests send pointers to a scratch folder.

It does not change any verdict.
