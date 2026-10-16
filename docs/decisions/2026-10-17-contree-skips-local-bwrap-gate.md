# Contree skips the local bubblewrap gate

**Date:** 2026-10-17  
**Status:** accepted

## Context

On Render, Contree was selected (`machine: contree`) but every check still exited `could_not_verify` with `bwrap: setting up uid map`. `test_pr` always called `sandbox_refusal()`, which requires local bubblewrap even when PR code is meant to run on Contree remotes. That gate made the hosted console motif fail.

## Decision

1. `sandbox_refusal(backend)` returns `None` when `backend == "contree"`.
2. Console Contree path also passes `--unsafe-no-sandbox` so a Contree→local mid-run fallback still works on hosts without bwrap.

## Consequences

- Hosted Contree checks can reach remote dual-runs.
- Local Contree CLI users no longer need working bubblewrap just to start.
