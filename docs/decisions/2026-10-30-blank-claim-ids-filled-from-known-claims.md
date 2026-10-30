# Blank probe claim ids are filled from the known testable claims

## What changed

On a product check, a model-written probe that names no claim id is no longer thrown away when testable claims
exist. The tool attaches each known testable claim to that probe. Each attached claim keeps the expectation the
claims step already recorded (`same` or `differs`). Its cover is the claim id followed by `.*`, which judging
links to observation names that start with that id.

The probe is still rejected when it cannot be linked. An id that is not one of the known claims is not replaced.
If no known claim can be attached, the probe is rejected with the same reason as before: it names no claim id
although testable claims exist. A probe that is kept therefore ends with claim ids on it.

Inputs just past an edited pattern's old match boundary are still added, and they are added after the claims are
filled, so a probe that arrived with a blank claims list is not dropped before those inputs exist.

A study run is unchanged. It does not fill claim ids.

The record lists the probes that were filled, under `probe_plan.model_claims_filled`.

## Why

A product check of an edited tag pattern came out could_not_verify. The claims step had three testable claims
(C1, C2, and C3) and the edited-pattern rule had fired on `rich/highlighter.py` line 85. The model then wrote
three probes and left every claims list empty. Those probes were rejected before any of them could run, so the
past-boundary inputs were never added and no probe exercised the changed line.

Asking the model again for claim ids does not cover this case. The first answer had no runnable probe, so the one
retry was spent on that. The retry's probes ran as code but still named no claim id, and they were rejected.

When the same style of probe is given claim ids by hand, and the saved past-boundary outputs from the same two
commits are replayed, the check reaches needs attention from a false claim. The missing step was keeping the
probes and attaching the known claims, not a new measurement.

## Decision

Prefer filling a blank claims list over dropping the probe.

- Fill only when the probe names no claim id, and only from claims the claims step already kept as testable.
- Do not invent an expectation. A known claim without `same` or `differs` is not attached.
- Do not replace an id the probe did write. If that id is not a known claim, the probe is rejected as before.
- If the probe already names at least one id, a blank entry beside it is dropped before the probe is checked,
  so that entry does not make the probe look unusable and does not replace it with another answer. The other
  known claims are not added. The model chose which claims to name.
- The end state of a kept probe still has claim ids. Filling is how a blank list meets that requirement. It does
  not relax it.
- The retry that asks the model to name claim ids stays. A retry that names ids is kept. Filling runs on the
  answer that is kept, when that answer is still blank.

## Alternatives and tradeoffs

- **Keep rejecting blank probes.** That is what the missed check did. The past-boundary inputs never run, and the
  result stays could_not_verify even when the probe code would have shown a difference.
- **Leave the claims list empty and still run the probe.** Differences then look unclaimed. A real difference
  becomes advisory and cannot confirm or refute a claim. The requirement that kept evidence is claim-linked
  would be gone.
- **Guess a claim from the wording of an observation.** A wrong link can turn a difference into proof, or into a
  false contradiction. The fill does not read observation names. It attaches the known claims, with covers that
  only match names starting with those ids. A difference whose name matches none of them stays advisory, as an
  unlinked difference does today.
- **Attach every known claim, including one that expects no change.** A "same" claim can then contradict an
  observation of the change the pull request meant to make. That can raise needs attention. Dropping the probe
  hides the past-boundary case entirely, so the fill is preferred. The record shows which probes were filled.

## What it means for you

A product check whose probes forget their claim ids can still run those probes, including the extra inputs just
past an edited pattern. The written probe lists the known claim ids. The plan records `model_claims_filled` so
the link is visible as a fill, not as something the model wrote.

If the probe names an unknown claim id, or there is no known claim to attach, it is still rejected and its
results do not count. A difference that the filled covers do not match stays advisory and does not, by itself,
raise needs attention.

## Offline proof

`tests/fixtures/claim_autofill/rich-4147-live191/` holds the miss: three rejection errors, claims C1, C2, and C3,
and the edited-pattern rule on `rich/highlighter.py` line 85. The run stored no probe source.

`tests/test_claim_autofill.py` checks three things.

- Blank claim ids on three probes are filled from C1, C2, and C3, and each probe still receives past-boundary
  inputs.
- An unknown claim id is still rejected. A probe that still cannot be filled is still rejected. A difference
  whose name matches none of the filled covers stays advisory.
- After the fill, replaying the saved past-boundary outputs of the same two commits (base `9d8f9a3`, head
  `3bd56b5`) reaches needs attention from a false claim on a past-boundary observation, under the seeded
  "behaviour kept" claim. Those outputs were already measured for the earlier offline proof. This check does not
  run the project again and does not call a model.
