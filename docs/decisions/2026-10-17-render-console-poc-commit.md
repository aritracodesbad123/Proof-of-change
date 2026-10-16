# Render console — stamp runs without a local `.git`

**Date:** 2026-10-17  
**Status:** accepted

## Context

The operator console Docker image (Render free tier) omits `.git` via `.dockerignore`. `daily_run` always called `sync_to_origin_main` on the Proof-of-Change checkout, so every hosted check exited immediately with `not a git repository`.

## Decision

1. **`resolve_poc_commit`:** if `.git` exists, keep fast-forwarding to `origin/main`; otherwise accept `POC_COMMIT` or Render’s injected `RENDER_GIT_COMMIT` (40-char hex) as the stamp for records.
2. **Install `bubblewrap`** in the console Dockerfile so the default local sandbox can start on Linux hosts that allow unprivileged user namespaces.

## Consequences

- Hosted checks no longer depend on bundling git history into the image.
- Local `make check` behavior is unchanged.
- If neither env SHA is set in a gitless image, the run still stops with a clear message.
