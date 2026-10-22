# Product runs stop on a refused GitHub login, and one run folder has one run

**Date:** 2026-10-22
**Status:** accepted

## What changed

- When GitHub answers 401 three times in a row for the same request on a product run, the run stops. It prints `auth problem: GitHub refused the login 3 times; the GitHub key in this run's environment is invalid or stale` and exits with code 3. The token is never printed.
- A product run takes an exclusive, non-blocking `fcntl.flock` on `run.lock` inside its run folder before it does any work. A second copy started on the same folder prints `another run holds the lock ...` and exits with code 4. The kernel releases the lock when the holding process exits, so a crashed run does not leave a stale lock.
- A single-PR product check names its run folder with seconds and the first PR number (`<date>-check-<HHMMSS>-pr<N>`), so two checks started in the same minute get different folders and locks. Other runs keep their folder names.
- Both safeguards apply only on the product route (`--product-check` with `--pr`). Study runs, bench mode and the daily study are unchanged: they take no lock, keep their folder names, and their GitHub client keeps the earlier retry behaviour on a 401.

## Why

A run whose environment held an out-of-date GitHub key kept retrying the same request instead of saying what was wrong, and two copies of the same run could work on one folder at once. Both wasted hours and made the results hard to trust.

## Decision

- Stdlib only (`fcntl`, `urllib`). No retry by repository name or special cases.
- The auth error is a `BaseException` so that per-repository `except Exception` handlers cannot turn a bad key into one "selection failed" line per library.
- Exit codes: 3 for the refused login, 4 for the held lock, distinct from the existing 1 and 2.
