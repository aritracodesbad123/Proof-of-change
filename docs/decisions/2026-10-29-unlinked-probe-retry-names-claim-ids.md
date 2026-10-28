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

`tests/test_unlinked_retry_claim_ids.py` uses the saved #4147 probe code and record (claim C1, probe model-p1 with
`claims: []`) under `tests/fixtures/unlinked_retry/`. With a stubbed retry naming C1 the probe ends up linked to C1,
and re-judging the saved runs still does not give `verified`. A retry naming no claim keeps the first answer and the
differences advisory. Retries with an unlinked probe, an unknown claim id, or fewer probes are not kept. No live
checks were run and no search credits were spent.
