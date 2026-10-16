# Operator console — live swarm + Nebius host

**Date:** 2026-10-16  
**Status:** accepted

## Context

Operators need a browser path to paste a GitHub PR URL, watch the check, and see which Nemotron agent is active — not only a Terminal log. Hosting on Nebius should reuse the same UI/API.

## Decision

1. **React/Vite + stdlib JSON API** (`console/web` + `poc/console_api.py`). Same `daily_run --pr` path as `make check`.
2. **Live progress** via `POC_PROGRESS_PATH` JSONL (`poc/run_progress.py`) written by `daily_run` / `agents.run_swarm`; jobs expose `stages`, `current_agent`, and `swarm` status for Ultra / Lightning / Super.
3. **UI:** NVIDIA-parallel dark theme (`#76B900`); swarm theater + stage runway on the job view (Emil motion gates: handoff/pulse, not poll thrash).
4. **Hosting:** Token Factory credits = models only. **Free public URL** = Render Blueprint (`render.yaml`) or local tunnel — not Streamlit (would rewrite the UI). Nebius Serverless AI Endpoint is optional and bills Compute. Local: `console_http` / `make console-host`. `orchestrate` enqueues via `start_check`. Advice-only; no merge blocking.
5. **G-ext:** posting still gated by `POC_DEMO_REPOS`; console may use `allow_any_repo` for read-only fetches when starting from Serverless.

## Consequences

- One active job per API process is enough for MVP (thread + progress file).
- Serverless request timeouts are avoided by acknowledging quickly and polling the job.
