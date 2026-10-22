# Product checks retry a Contree API timeout a few times

**Date:** 2026-10-22
**Status:** proposed

## What changed

- On a product check (`--product-check` with `--pr`), a Contree request that fails with a transient error is tried again. Transient means the API timed out (for example `ApiTimeoutError`) or answered with a server error (HTTP status 500 to 599).
- There are at most 3 tries in all, with a wait of 5 seconds before the second try and 15 seconds before the third (this growing wait is called backoff).
- If every try fails, the check ends exactly as before, with the same reason, for example `contree request failed: ApiTimeoutError`. Nothing ever falls back to running the pull request locally.
- Only the start of a run is retried: opening the image (`images.use` or `images.oci`) and creating the run. Once Contree has created the run, any failure while waiting for it, including a timeout or a 5xx, is final and keeps its original reason. The Contree SDK cancels a run when waiting on it fails, so the same run cannot be polled again, and a second run is never started. Pull request code therefore runs at most once per step.
- Each step has one overall deadline: its own timeout plus 120 seconds. A retry is skipped, and the original error kept, when the time left (after the backoff wait) is shorter than the step's timeout. A step can no longer take about three times its limit.
- To tell a start failure from a wait failure, the session watches the SDK's run-creation call (`_start_operation`, SDK 0.3.6). If that call is not available, every failure counts as "may have started" and nothing is retried.
- A refused login (HTTP 401 or 403) and any other kind of error are not retried.
- Study runs, bench mode and the daily study are unchanged: they still make one try.

## Why

In the 22 October rerun, one product check ended as could not verify only because a single Contree request timed out while preparing the two sides. A short, bounded retry gives such a blip a second chance without hiding a real outage.

## Decision

- Retry inside the Contree session, only the start of each run, and only when the session was started for a product check.
- Never retry after the run exists, so a slow wait can never launch a second copy of the pull request's code or leave an extra saved image behind.
- Keep the number of tries small and fixed, so a real outage still fails within about 20 extra seconds of waiting.
- Re-raise the last error unchanged, so the reason in the record stays the same.

## Alternatives and tradeoffs

- Retrying the whole check would repeat work that already succeeded and take much longer.
- Unlimited retries could hang a check during a real outage.
- Polling the same run again after a wait timeout would be better than failing, but SDK 0.3.6 cancels the run when the wait fails and has no public way to re-attach, so we fail with the original reason instead.
- Cost: a create request that times out on our side might still have been accepted by Contree. That case cannot be told apart from a lost request, so in that narrow case a retry could create a second run. A wait timeout, the case seen in the rerun, is never retried.
- Watching `_start_operation` relies on an SDK internal. The SDK version is pinned, and if the internal goes away the code fails closed (no retries).

## What it means for you

A product check is less likely to end as could not verify because of one slow Contree answer. If Contree is really down, you see the same message as before. Nothing changes for you to do.
