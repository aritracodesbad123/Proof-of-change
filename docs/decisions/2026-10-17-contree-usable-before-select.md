# Contree only when the SDK is actually importable

**Date:** 2026-10-17  
**Status:** accepted

## Context

With `NEBIUS_PROJECT_ID` set on Render, the console passed `--sandbox-backend contree` while the image lacked `contree-sdk`. `daily_run` then fell back to local bubblewrap, which cannot create uid maps on Render → every check became `could_not_verify`. The console motif (paste a PR, watch a real run) failed.

## Decision

1. `contree_usable()` is true only with API key + project id **and** an importable `contree_sdk`.
2. Console image installs `.[ops,contree]` so Contree can run when credentials are set.
3. If Contree is not usable and bwrap cannot start, keep auto `--unsafe-no-sandbox` so hosted demos still execute.

## Consequences

- Health `contree_ready` matches reality.
- Env-only Contree no longer traps the console into a dead local-sandbox path.
