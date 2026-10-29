# The unlinked-probe retry is sent the claim ids and must name one per probe

## Problem

On the rich #4147 live check the probe ran cleanly and saw 8 differences, and claim C1 described exactly that
change, but the probe came back with `claims: []`. The retry for unlinked probes only repeated the generic rule,
so it again named no claim and all 8 differences stayed advisory.

## Change

`poc/model_probes.generate`: when testable claims exist and no usable probe names one, the retry now includes the
testable claim list (id, expected outcome, text) and states that every probe must list at least one of those ids
(`unlinked_retry_rule`). The retry is kept only when `unlinked_retry_weakens` finds nothing:

- every usable retry probe names at least one known claim id;
- the #177 rules in `retry_weakens` still apply (at least as many usable probes, no claim matching fewer
  observation names). Only its "fewer unmatched covers" step is skipped here, because a first answer with no linked
  claim has no covers to compare against; unmatched covers are still recorded as before.

Otherwise the first answer is kept and `retried.kept_first_answer` says why.

## Not done, on purpose

Probes are never linked to a claim by name match or any other heuristic. A link comes only from the model's answer;
a wrong automatic link could turn a difference into proof. If the retry names no claim, the differences stay
advisory exactly as today. No guard test is weakened and no uncovered difference is made quieter.

## Tests

`tests/test_unlinked_retry_claim_ids.py` uses the saved #4147 probe code and record (claims C1 and C2, probe
model-p1 with `claims: []`) under `tests/fixtures/unlinked_retry/`. Verdicts are recomputed with
`ops/daily_run.rejudge_probes` and `verdict_for` from the saved probe runs and test comparison. `final_verdict.final`
returns a gated record unchanged, so it cannot test a re-judge. The tests check the exact verdict and reason:

- unlinked (as saved): could_not_verify, "probe(s) model-p1 have no linked claims ...";
- C1 covering `c1.*` only: could_not_verify (`advisory_unclaimed_difference`), naming the uncovered `c2.*`
  differences;
- every difference covered: verified.

The retry tests check four cases:

- A stubbed retry naming C1 is kept and links C1.
- A retry naming no claim keeps the first answer, so the differences stay advisory.
- Retries with an unlinked probe, an unknown claim id, or fewer probes are not kept.
- The #177 cover retry still rejects a retry that does not leave fewer unmatched covers.

No live checks were run and no search credits were spent.

## Reason text for linked probes

When a probe links claims but some of its differences fall outside its covers and are advisory, `verdict_for`
(and the probe summary) now name those differences ("difference(s) no linked claim covers (model-p1
c2.adjacent_spans, ...)") instead of saying the probe has no linked claims. The verdict and the
`advisory_unclaimed_difference` flag are unchanged, and `_keep_advisory` is unchanged. A probe with no claims keeps
the old text.

## What this means for rich #4147

Linking alone cannot flip #4147. Tonight's probe records the same inputs twice, under `c1.*` and under `c2.*`.
Linking C1 to `c1.*` proves C1 and leaves the `c2.*` copies as uncovered advisory differences, so the check stays
could_not_verify. Those `c2.*` differences are inputs the fix is meant to change. Reading them as a broken "same"
claim would be a false alarm, so no "every same claim must be named" rule was added.

None of the saved #4147 copies is a confirmed catch:

- rerun-final's needs_attention was a false alarm. Its claim C4 expected a brand-new regression test to "pass" on
  both sides, and the test cannot pass on main.
- live140's needs_attention (`C2.space_after` lost its tag highlighting) needs human review before it counts.

Expect more `retried.kept_first_answer` outcomes, where the retry is not kept and the differences stay advisory.
