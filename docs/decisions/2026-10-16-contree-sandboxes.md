# Contree Token Factory Sandboxes for probe + pytest dual-runs

**Date:** 2026-10-16

## Decision

Wire Nebius Token Factory Sandboxes (Contree SDK 0.3.6) as an optional backend for **source-pair** probe and pytest dual-runs. Auth is `NEBIUS_API_KEY` + `NEBIUS_PROJECT_ID` (same key family as Token Factory models). There is no `CONTREE_API_KEY`.

## Behaviour

- `--sandbox-backend local` (default): bubblewrap via `guardrails/sandbox.py`.
- `--sandbox-backend contree`: when both env vars are set and `contree-sdk` is installed (`pip install -e '.[contree]'`), build a main checkpoint (`disposable=False`), fork a PR checkpoint, then run every mapped pytest and every frozen probe on both checkpoints (`disposable=True`) under a ≤40 concurrent-op semaphore.
- Missing credentials or SDK → **explicit** fallback to local bubblewrap (never silent). `POC_REQUIRE_CONTREE=1` refuses instead.
- Secrets never enter Contree shell env (orchestrator-only keys; untrusted runs use Contree's image env only).
- Record fields: `machine`, `sandbox_backend`, `sandbox_backend_note`, `contree: {main_uuid, pr_uuid, ...}`.
- Coverage and test mapping stay on local checkouts; Contree owns the dual-run execution for probes/pytest when active.
- Nightly/source-build routes stay on local bubblewrap until Contree install paths are proven there.

## Why

Untrusted PR code should be able to run in Nebius private sandboxes, not only on the operator's Mac. Contree checkpoints give a clean main copy and a PR copy without sharing a writable filesystem between disposable dual-runs.

## Alternatives rejected

- Stub-only Contree markers without remote execution.
- A separate `CONTREE_API_KEY` (SDK already reads Nebius IAM vars).
- Silent fallback when project id is missing.
