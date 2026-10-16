# Render console — sandbox fallback when bwrap cannot start

**Date:** 2026-10-17  
**Status:** accepted

## Context

After gitless `POC_COMMIT` stamping, Render checks still produced `could_not_verify`: bubblewrap cannot set up a uid map (`Operation not permitted`) on Render’s free Docker runtime. Contree needs `NEBIUS_PROJECT_ID`; many demo deploys only set `NEBIUS_API_KEY`.

## Decision

1. Console-started checks (`poc.console_api.console_run_flags`): Contree only when **creds and `contree-sdk` are both present** (`contree_usable`). Env vars alone must not select Contree (that previously fell back to broken bwrap on Render and killed the console motif).
2. Console image installs `.[ops,contree]` so Contree can run when `NEBIUS_PROJECT_ID` is set.
3. Otherwise, if local bubblewrap cannot start, auto-pass `--unsafe-no-sandbox` so a public-PR demo can still execute. `POC_UNSAFE_NO_SANDBOX=0` refuses the fallback.
4. Health JSON reports `contree_ready` / `run_flags` / `run_note` so operators can see which path a host will take.

## Consequences

- Free Render demos work without Contree; PR code runs outside bubblewrap on that host.
- Prefer Contree (or a machine with working bwrap) for anything beyond a throwaway demo.
