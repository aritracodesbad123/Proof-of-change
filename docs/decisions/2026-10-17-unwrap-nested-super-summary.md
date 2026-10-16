# Unwrap nested Super summary JSON

**Date:** 2026-10-17  
**Status:** accepted

## Context

Super sometimes returns `explanation.text` as a JSON string (`{"summary":"..."}`) instead of plain prose. The console either looked empty or showed raw JSON.

## Decision

Normalize in `poc/agents.py` after the swarm call, and unwrap again in the console UI for records already written.

## Consequences

- Existing Render runs with nested text become readable after UI deploy.
- Future records store plain English in `explanation.text`.
