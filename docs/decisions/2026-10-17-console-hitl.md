# Console HITL mid-check (claims / probes / business scenarios)

**Date:** 2026-10-17  
**Status:** accepted

## Context

Operators need to review AI-drafted claims and probes before freeze, and inject multiple business scenarios. Bench and CLI must stay non-interactive; the operator console must always pause.

## Decision

1. **`POC_HITL=1` + `POC_HITL_DIR`** — console `start_check` always sets both per job under `ops/runs/_jobs/<id>/`. Bench/CLI omit them unless explicitly set.
2. **`await_human` stage** — after model draft (before freeze), write `hitl_draft.json` (claims, probe previews, `needs_business_followup`, 1–3 business questions), emit `await_human`, poll for `hitl_approval.json` (~2h).
3. **Approval** — `{ approve: string[], extra_scenarios: string[], business_answers: {}, skip_business_followup: bool }`. Continue is blocked (HTTP 400) when business follow-up is required and unanswered unless skipped. Cap ~20 scenarios.
4. **Extras** — each scenario (plus non-empty business answers) gets a gated model probe; `validate_probe` + `probe_quality.lint`; then freeze and continue probes → pytest → verdict → agents → report.
5. **UI** — job layout left = swarm + HITL, right = ProcessFlow, bottom = always-on live log (`console.log` tee, ~8KB tail per poll).

## Consequences

- Freeze timing moves after human approval when HITL is on; non-HITL path unchanged.
- Jobs surface `status: awaiting_human` and `hitl_draft` until approval is written.
