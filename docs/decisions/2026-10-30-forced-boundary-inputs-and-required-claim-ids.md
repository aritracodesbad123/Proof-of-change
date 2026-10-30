# Forced past-boundary probe inputs and required claim ids (2026-10-30)

## Why
The third live rich#4147 run (live188, main 3a13236) was an honest miss: could_not_verify. The model's probe
recorded real, non-empty spans, but every input sat fully inside the old match (`<a>foo</a>`, `<a>foo</a> <b>bar</b>`),
so nothing tested just past the boundary, and the probe named no claim id (`claims: []`).

## What changed (product checks only)
1. **Forced past-boundary inputs** (`poc/boundary_claims.force_inputs`, called from `model_probes.generate` when the
   boundary rule fires). Each probe input that the edited pattern's old text matches completely gets three siblings
   (`<name>_pb_space` = input + " tail", `_pb_text` = input + "tail", `_pb_newline` = input + "\ntail"). We never
   add a bare trailing newline. The added inputs only feed the calls the model wrote, before freezing (base-side code
   only). They are listed on the record as `probe_plan.model_forced_boundary_inputs`. `boundary_claims.input_for`
   maps an observation such as `c1.single_pb_text_spans` to its input (the longest input name joined with "_").
2. **Claim ids required.** When testable claims exist, a probe with `claims: []` is rejected
   (`UNLINKED_PROBE`). The empty-probe retry now also sends the claim ids (`unlinked_retry_rule`), so the model is
   asked for ids before anything is rejected. No extra model call was added.

## Offline proof (`tests/test_boundary_force.py`)
- The live188 record and probe, with forced inputs run for real against rich base 9d8f9a3 and head 3bd56b5
  (`forced_outputs.json`). Past-boundary inputs differ (for example `single_pb_text`: 6 spans on main, 2 on the PR).
- With the probe tied to the model's own claim ids (C1 and C2 "differs"), the replay reaches **needs_attention**
  from `false_claim` on `_pb_` inputs only, under the seeded `C2-kept`/`C3-kept` claims.
- With the recorded inputs, there is no past-boundary false_claim. With the recorded unlinked probe, the result is
  could_not_verify, as it was live.
- Mutations: removing the reject, removing the forcing call, or making the forcing a no-op each fail a test.
- The trigger (`modified_patterns`) is unchanged, so the 13 safe candidates stay silent (`test_boundary_probes`).

## Open
- The proof links C1 and C2 by hand. A live run still depends on the model naming claim ids after the retry. If it
  doesn't, the probe is rejected and the run is honestly could_not_verify.
