# Replay data for the results page

This folder is what the GitHub Pages results page shows. The page is a static build of the
operator console in replay mode. It reads these files and does not install a library or call an API.

`catalog.json` lists the checks. Each `checks/<id>/` folder holds `record.json` and, when a
report was already written, `REPORT.html`.

## Export

From the repository root, after a check has finished:

```bash
python ops/export_replay.py
```

By default that command copies the curated examples already in the repo, then any finished records it finds
under `ops/runs` and `reports/daily`. It keeps the verdict already stored on the record or already
printed on the report. It does not compute a new one. Values that look like keys are removed.

Useful flags:

```bash
python ops/export_replay.py --runs ops/runs --reports reports/daily --out replay
```

Commit the updated `replay/` folder and push to `main`. The Pages workflow publishes it.
The same files are copied into the console build; do not commit `console/web/public/replay/`.

The page currently shows only the 30-PR batch on code version 0fa0016:

```bash
python ops/export_replay.py --runs benchmarks/batch30-0fa0016/runs --reports /nonexistent --no-curated
```

Older checks are in `benchmarks/replay-archive/`.
