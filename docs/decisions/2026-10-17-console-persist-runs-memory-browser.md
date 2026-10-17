# Console keeps finished runs in memory + browser

**Date:** 2026-10-17  
**Status:** accepted

## Context

On Render free tier the filesystem is wiped when the service sleeps or redeploys. Operators finished checks, refreshed, and saw an empty Recent runs list — or a Failed job whose log only said `run log: …/REPORT.md` with no reason. The console motif requires the analysis to remain visible after a run.

## Decision

1. After each check, snapshot the `record.json` into an in-process `_recent_runs` cache; `/api/runs` and `/api/runs/<id>` merge disk + memory.
2. Job finish packs stderr-first log tails, sets `error`/`warning` from `Stopped:` / `run_meta.problems`, and attaches the record so the UI can open analysis even when exit ≠ 0.
3. The SPA caches finished records in `localStorage` and auto-navigates to the run view when a job completes successfully.

## Consequences

- Survives Render sleep for the same browser / same API process; still lost on a brand-new device after redeploy until the next check.
- Failed jobs show the real failure text instead of a blank runway.
