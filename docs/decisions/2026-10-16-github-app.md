# GitHub App for demo/mirror repos (G-ext)

**Date:** 2026-10-16

## Decision

Ship a GitHub App surface that posts **only** to allowlisted demo/mirror repos (`POC_DEMO_REPOS`): webhook → `/prove` or PR sync → `ops/daily_run` → hosted behavior-map HTML → non-blocking check run + one summary comment.

## Behaviour

- Check-run conclusion is always `success` or `neutral` — never `failure` (never blocks merge).
- Without `GITHUB_APP_INSTALLATION_TOKEN` (or App JWT mint via optional `.[github]`), `apply()` dry-runs: writes `reports/hosted/*.html`, does not post.
- Webhook: stdlib `python -m poc.github_app` (`POST /webhook`, `GET /health`); HMAC via `GITHUB_WEBHOOK_SECRET`.
- Write paths are marked `# br-allow-external:` and gated by `may_post`.

## Out of scope here

Nebius Serverless live deploy, Contree MCP process hosting, Tavily, posting outside the allowlist.
