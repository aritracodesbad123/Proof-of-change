# Nemotron agent swarm (advisory Ultra / Lightning / Super summary)

## What changed

A thin coordinator (`poc/agents.py`) routes post-verdict work to role-specific Nebius models:

| Role | Default model | Job |
|---|---|---|
| judge | Ultra 550B | Label findings (proven / false / unmentioned / needs_human) + one sentence |
| helper | Lightning (Nano fallback) | Suggest noise patterns / install hints |
| summary | Super 120B | Plain-language report text; quotes must appear in the record excerpt |

Claims and probes stay on Super via `poc/model_probes.py`. The code verdict in `poc/verdict.py` remains authoritative: Ultra labels are stored on the record and shown in the report as advisory. `ops/daily_run.finish` runs the swarm after the verdict and before the record is written. CLI flags: `--judge-model`, `--helper-model`, `--summary-model`. Recorded fixtures cover the new tasks so CI needs no live key.

Phases B–D land as thin, gated surfaces in the same change set: Contree backend select (`--sandbox-backend`, `CONTREE_API_KEY`), GitHub App allowlist + hosted HTML report, Serverless plan entrypoints, Contree MCP tool contract, optional Tavily lookup (`TAVILY_API_KEY`).

## Why

REQUIREMENTS §4a asks for a multi-model swarm. Feeding Ultra into the score before evals would let the model silently disagree with the code verdict. Advisory-first matches the README honesty rule and keeps merge advice code-owned.

## Decision

- Ultra / Lightning / Super-summary are advisory until evals show Ultra is safe to feed the score.
- Swarm runs only when a model provider is selected; recorded fixtures exercise the path in CI.
- Contree without a key falls back to local bubblewrap; machine field records `contree` vs `local` when selected.
- GitHub App writes only to `POC_DEMO_REPOS` (G-ext).

## Alternatives and tradeoffs

- Wire Ultra into `poc/verdict.py` now — rejected until PatchGuru / blind evals agree.
- Contree SDK dual-run in this PR — deferred: key + SDK checkpoint/fork still stubbed; local bubblewrap remains the executor.

## What it means for you

- Live Nebius runs now call judge/helper/summary after the code verdict; the report shows an AI summary and advisory labels.
- CI and `--model-provider recorded` need no live key; fixtures cover the new roles.
- Contree, GitHub App, Serverless, MCP and Tavily are callable modules; set the matching env vars when you want those backends live.
