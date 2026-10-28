# A "this changes" claim is met per input when one checked value differs

Status: proposed

## What changed

A probe input often reports several values for one claim, for example `case1.title_present` and
`case1.rel_present`. Before, every value linked to a claim that says something changes had to differ.
A value that rightly stayed the same was labelled "does not differ although the claim says it does" and
made the verdict needs attention.

Now, for each input (the dotted observation name without its last part), when at least one value of a
claim differs as claimed, the claim is met for that input. That input's other values for the same claim
that stayed the same are listed as advisory only and no longer decide the verdict. The report text names them.

Unchanged:
- An input where no value of the claim differs still needs attention.
- A value from another claim, or an undotted name (its input cannot be told apart), does not count.
- A value that differs although the claim says it does not, or a difference no claim covers, still needs
  attention.
- A value that is unstable only on the pull request keeps its own rule.
- Removing a flag can raise a verdict. That is what this rule does for requests #7520, which moves from needs_attention to could_not_verify. The check that it changes nothing else is the re-judge of all 74 stored benchmark records with the old and new code (`scripts/rejudge_records.py`). Only requests #7520 changes.

The rule is general: there is no project, package or per-repo setting.

## Why

On requests #7520 the claim said the Link header now keeps the `title` value. On the one input, `title`
appeared as claimed and `rel` rightly stayed present on both sides. The stayed-the-same value was still
required to change, which gave a false needs attention.

A first version counted a difference anywhere in the claim. Re-judging the recorded benchmark showed it
also flipped The-PR-Agent #4189 from needs attention to verified, where two whole inputs showed no
change. Scoping the rule per input keeps that verdict.

## Evidence

Every recorded run with probe results (74 records: the benchmark results, the 30-PR batch, the replay
checks, the 2026-10-27 run and the broad-claims branch live run) was re-judged from its recorded probe
runs with the old and new rules. Only requests #7520 changes: needs attention to could not verify. It is
not verified because claim C3 still has no matching observation. The live rich #4147 record stays needs
attention.

Tests: `tests/test_claim_one_difference.py`.
