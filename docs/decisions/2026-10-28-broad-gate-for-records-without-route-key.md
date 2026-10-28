# Re-judging applies the broad-claims gate to records without a product_check key

## Context

Re-judging applied the broad-claims gate (poc/broad_claims.py) only when a saved record had `product_check`
set. Records written before that key existed have no key at all, so they skipped the gate and a broad claim in
them could still count as checked.

## Decision

`ops/daily_run.broad_gate_for(rec)` decides: the gate applies on the product route and also when the key is
missing. Only an explicit `product_check: false` skips it. A missing key cannot tell which route wrote the
record, so it gets the stricter reading; the gate only holds claims back and never releases a saved hold.
`rejudge` and both re-derivations in `evals/checks.py` use it. The other product-only steps on re-judging (the
advisory carry-over) still follow `product_check` itself, so nothing else about such a record changes.

## Where it still cannot apply

- A record with no probe items: there is no claim to hold back.
- A record without a saved comparison or its JUnit files: `rejudge` returns it unchanged, so nothing is
  recomputed for it, the gate included. Those records keep their saved verdict until they are run again.
