# Console on Render needs GITHUB_TOKEN

**Date:** 2026-10-17  
**Status:** accepted

## Context

Paste-a-PR on the free Render console failed with `GitHub rate limit hit … (remaining=None)`. `GitHub` already supports `GITHUB_TOKEN`, but the Blueprint only listed Nebius secrets. Anonymous GitHub API is 60 requests/hour and shared across Render exit IPs.

## Decision

1. Require a read-only `GITHUB_TOKEN` (or `GH_TOKEN`) on the hosted console; document it and add it to `render.yaml` as a dashboard secret.
2. Rate-limit errors without a token tell the operator to set one.

## Consequences

Operators create a fine-grained or classic read-only PAT and set it once on Render. Authenticated limit is 5 000/hour. Token stays in the parent process; untrusted PR envs still strip it.
