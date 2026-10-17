# Console job finish must not nest `_jobs_lock`

**Date:** 2026-10-17  
**Status:** accepted

## Context

After a Render check reached the report stage, the UI froze and `POST /api/checks` / `GET /api/runs` stopped responding while `/api/health` still worked. The free instance looked “killed,” but the process was wedged.

## Decision

Job finish called `remember_run` (which acquires `_jobs_lock`) while already holding `_jobs_lock`. With a non-reentrant `Lock` that deadlocks forever and blocks every endpoint that needs the lock.

1. Call `remember_run` *before* taking the lock when updating the job.
2. Use `threading.RLock` so accidental nesting cannot wedge the console again.

## Consequences

A finished check no longer freezes the console. Operators still need a Render restart/redeploy to clear an already-deadlocked process. Free-tier kills/timeouts remain a separate hosting limit.
