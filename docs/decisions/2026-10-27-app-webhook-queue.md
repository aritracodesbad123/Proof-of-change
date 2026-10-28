# The GitHub App answers webhooks at once and runs checks from a one-at-a-time queue

## What changed

`poc/github_app.py` used to run the whole check inside the webhook request. GitHub stops waiting after
10 seconds, so every delivery showed as timed out, and a retry or redelivery could start the same check twice.

Now the webhook:

1. Checks the `X-Hub-Signature-256` signature first. A bad signature gets 401 and nothing is recorded or queued.
2. Requires an `X-GitHub-Delivery` ID and records it in `deliveries.txt` under the state dir
   (`$POC_OPS_DIR/github-app`, or `ops/github-app` when `POC_OPS_DIR` is unset). The file is read and appended
   under an exclusive `fcntl` lock, so a duplicate is skipped (200, `duplicate: true`) even after a restart.
3. Puts a check plan on an in-memory queue and replies **202** straight away. Events that are ignored or refused
   still get a quick 200 with the plan.

One worker thread takes plans in order and runs one check at a time.

Before each check, the worker charges it to the console's daily counter (`console_api.hosted_budget_refusal`,
the same `_console_daily.json` under `POC_OPS_RUNS`). This happens on a hosted deploy only (`POC_HOSTED=1`, Render
or a Space), the same rule the console uses. So App checks and console checks share `POC_DAILY_CAP`. That call
also refuses when `POC_TAVILY_CREDIT_CAP` is unset. A refused check is logged and not run.

The console and the App are separate processes, so the counter's read-and-write now takes an exclusive `fcntl`
lock on `_console_daily.json.lock`, and the new value is written to a temporary file and renamed into place. The
thread lock stays for threads in one process. A test starts six processes against a cap of 3 and gets exactly
3 checks through.

## Limits

- The queue is in memory. If the listener restarts, queued checks are lost, and because their delivery IDs are
  already recorded, a manual redelivery of the same delivery is skipped. Ask for a new check with a new
  `/prove` comment or a push.
- A refused check (daily cap reached) posts nothing to GitHub; it shows only in the listener's log.
- `deliveries.txt` grows by one short line per delivery; at hackathon volume this does not matter.
