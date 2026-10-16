# Render console — sandbox fallback when bwrap cannot start

**Date:** 2026-10-17  
**Status:** accepted

## Context

After gitless `POC_COMMIT` stamping, Render checks still produced `could_not_verify`: bubblewrap cannot set up a uid map (`Operation not permitted`) on Render’s free Docker runtime. Contree needs `NEBIUS_PROJECT_ID`; many demo deploys only set `NEBIUS_API_KEY`.

## Decision

1. Console-started checks (`poc.console_api.console_run_flags`): if Contree credentials are present, pass `--sandbox-backend contree`.
2. Otherwise, if local bubblewrap cannot start, auto-pass `--unsafe-no-sandbox` so a public-PR demo can still execute (note emitted on the job). `POC_UNSAFE_NO_SANDBOX=0` refuses the fallback.
3. Health JSON reports `run_flags` / `run_note` so operators can see which path a host will take.

## Consequences

- Free Render demos work without Contree; PR code runs outside bubblewrap on that host.
- Prefer Contree (or a machine with working bwrap) for anything beyond a throwaway demo.
