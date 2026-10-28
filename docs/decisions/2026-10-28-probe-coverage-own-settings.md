# Probe coverage uses only our own coverage settings

The test coverage run already passes its own settings file (`--cov-config`). The probe coverage runs (local and Contree) called `coverage run` and `coverage json` without one, so the project's settings applied:

- its `[run] source` beat our `--include` ("--include is ignored because --source is set"), so nothing on the changed files was recorded;
- its `parallel = true` renamed the data file, and `coverage json` then combined every file sharing the prefix, including our own log, which failed with "file is not a database";
- its `fail_under` applied to the report and made it exit 2.

Now every probe coverage command gets `--rcfile` pointing at our own file (`PROBE_COVERAGE_RC`: the test run's settings plus `parallel = False` and `fail_under = 0`). With `--rcfile`, coverage reads no project file. In Contree the data file and log no longer share a prefix. This only lets the measurement happen; it never raises a verdict by itself.

Test: `tests/test_probe_coverage_own_settings.py` runs coverage on a project whose settings set all three; without our file each failure reproduces.
