# Product checks retry a Contree API timeout a few times

**Date:** 2026-10-22
**Status:** proposed

## What changed

- On a product check (`--product-check` with `--pr`), a Contree request that fails with a transient error is tried again. Transient means the API timed out (for example `ApiTimeoutError`) or answered with a server error (HTTP status 500 to 599).
- There are at most 3 tries in all, with a wait of 5 seconds before the second try and 15 seconds before the third (this growing wait is called backoff).
- If every try fails, the check ends exactly as before, with the same reason, for example `contree request failed: ApiTimeoutError`. Nothing ever falls back to running the pull request locally.
- A refused login (HTTP 401 or 403) and any other kind of error are not retried.
- Study runs, bench mode and the daily study are unchanged: they still make one try.

## Why

In the 22 October rerun, one product check ended as could not verify only because a single Contree request timed out while preparing the two sides. A short, bounded retry gives such a blip a second chance without hiding a real outage.

## Decision

- Retry inside the Contree session, around each request, only when the session was started for a product check.
- Keep the number of tries small and fixed, so a real outage still fails within about 20 extra seconds of waiting.
- Re-raise the last error unchanged, so the reason in the record stays the same.

## Alternatives and tradeoffs

- Retrying the whole check would repeat work that already succeeded and take much longer.
- Unlimited retries could hang a check during a real outage.
- Cost: a request that times out on the client side might still have finished on the server, so a retry can repeat a setup step. Each setup step starts from a fixed image, so repeating it gives the same result.

## What it means for you

A product check is less likely to end as could not verify because of one slow Contree answer. If Contree is really down, you see the same message as before. Nothing changes for you to do.
