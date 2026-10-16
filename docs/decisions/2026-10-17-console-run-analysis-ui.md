# Console run view shows full PR analysis

**Date:** 2026-10-17  
**Status:** accepted

## Context

Operators saw `Claims: None`, cryptic `C1`–`C4` probe rows, and `(no AI summary)` even when the record held `probe_plan.model_claims`, per-observation results, Ultra labels, and Lightning notes. Super sometimes returned empty `explanation.text`.

## Decision

1. Run detail UI reads claims from `probe_plan.model_claims` (fallback: probe-nested claims), shows claim text + expect + PR quote + observation outcomes.
2. Show probes with covered claim ids and observation labels; project-test glance from `comparison`; Ultra/Lightning advisory sections.
3. If Super text is empty, fill `explanation.text` from code verdict/reason (and UI synthesizes a narrative from claims + Lightning for older records).

## Consequences

- Existing finished runs become readable without re-running.
- Future swarm summaries are never blank in the console.
