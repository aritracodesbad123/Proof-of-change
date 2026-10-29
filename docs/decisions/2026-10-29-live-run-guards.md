# Live-run guards for a watched check

Date: 2026-10-29

## Decision

- **`--require-boundary-rule FILE:LINE`.** After the probe plan is written to the record, the run stops unless the edited-pattern rule found exactly that one entry. A different entry, an extra one or none at all all stop it. The check sits at the end of `plan_probes`, which every route calls before any pull-request code runs. The flag also turns off `POC_PARALLEL`, so no PR checkpoint build overlaps planning.
- **`--max-provider-calls N` and `--max-cost-usd USD`.** These are checked inside the Nebius provider, just before each call is sent.
  - The call that would be number N+1 is refused.
  - A call is also refused when spend so far plus that call's worst case would pass USD. The worst case is input at 2 characters a token plus the full output budget.
  - Calls whose usage the server did not report stay at their worst case.
  - A refusal stops the whole run. The key check (`GET /models`) is not a model call and is not counted.
- **`--require-contree` never retries a Contree timeout.** Product checks used to retry a Contree API timeout or 5xx before a run started, up to 3 tries. Under `--require-contree` that retry is now off: the first timeout gives "could not verify" and nothing is retried.
- All stop reasons are plain text and never contain a key.

## Why

A watched live check has to stop by itself at the agreed points (wrong trigger, a 5th call, $0.10), not by someone killing it.

## Not changed

- Every flag is off by default, so runs without them behave as before.
- Product checks without `--require-contree` keep the start-up retry.
- No verdict or prompt changes.
