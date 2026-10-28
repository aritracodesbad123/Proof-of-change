# Every folder the services write to is a setting, so the app code can stay read-only

## What changed

On the Nebius VM the app code under `/opt/proof-of-change` belongs to root and the services can write only to
`/var/lib/proof-of-change`. Some writes still went into the code folder by fixed path. Each now has a setting;
when the setting is unset, the old path is used, so local runs behave as before.

| Write | Setting | Default (unchanged) | On the VM |
| --- | --- | --- | --- |
| Hosted HTML reports, written by `poc/github_app.py` and read by `poc/console_api.py` | `POC_HOSTED_REPORTS_DIR` (new) | `reports/hosted` | `/var/lib/proof-of-change/reports/hosted` |
| Console job folders (`_jobs/<id>`: progress, console log, operator approval) | `POC_OPS_RUNS` via `RUNS_ROOT`; the old fallback to `REPO_ROOT/ops/runs/_jobs` is gone | `ops/runs/_jobs` | `/var/lib/proof-of-change/runs/_jobs` |
| Run folders the App looks in for a finished record | `POC_OPS_RUNS` (already used by the console) | `ops/runs` | `/var/lib/proof-of-change/runs` |
| An App check's run folder, `seen_prs.json` and work folder (`daily_run --ops-dir`) | `POC_OPS_DIR` (already used by the console) | `ops` | `/var/lib/proof-of-change` |
| An App check's reviewer reports (`daily_run --report-dir`) | `POC_REPORT_DIR` (already used by the console) | `reports/daily/<run>` | `/var/lib/proof-of-change/reports/daily` |
| Heavy-build slots | `POC_HEAVY_BUILD_DIR` (already in `ops/daily_run.py`) | `ops/work/heavy-builds` | `/var/lib/proof-of-change/work/heavy-builds` |

Run folders reuse the existing `POC_OPS_RUNS` rather than adding a second name for the same folder.

- **GitHub App.** It now passes `--ops-dir` and `--report-dir` to the check from `POC_OPS_DIR` and `POC_REPORT_DIR`,
  the same way the console already did. Before this change an App check wrote under `ops/` and `reports/daily/` in
  the code folder.
- **Writes from the webhook queue are already covered.** The delivery list is under `$POC_OPS_DIR/github-app`, and
  the shared daily counter is under `POC_OPS_RUNS`.
- **Setup and health check.** `setup.sh` creates every one of these folders, owned by the service user.
  `healthcheck.sh` writes and then removes a small file in each one, as that user.
- **No links.** No links into the code folder are used.

Other `REPO_ROOT` paths were checked and are not the same kind of write:
- **Read-only lookups:** the schema, the tracked-libraries list, `ops/local.json`, the web page files and `.git`.
- **Writes that already have a setting:** the accounts file (`POC_ACCOUNTS_FILE`), heavy builds (`POC_HEAVY_BUILD_DIR`), and `daily_run`'s `--ops-dir`/`--report-dir` defaults, which both the console and the App now pass.
- **Git sync:** used only by daily study runs on a git checkout; the VM's copy has no `.git`.

Tests that point `console_api.REPO_ROOT` at a temporary folder now also point `RUNS_ROOT` there, so they never write job folders into the real checkout.

## Tests

`tests/test_data_folder_settings.py` checks that the App writes its hosted report to `POC_HOSTED_REPORTS_DIR` and
the console builds its hosted path from the same setting. It also checks that the App reads run folders from
`POC_OPS_RUNS`, passes `--ops-dir`/`--report-dir`, and keeps the old defaults when the settings are unset. Another
test checks that both service files set every one of these settings under `/var/lib/proof-of-change`.
