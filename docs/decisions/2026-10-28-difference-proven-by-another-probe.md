# A difference another probe proves is advisory, not unclaimed

Probes of one PR often print each other's observations, so a difference one probe proves for its claim was flagged as unclaimed, or as contradicting a "same" claim, in a sibling probe that printed it too.

Now such an observation is advisory ("the same difference is proven by a claim in another probe, check"), but only when both of these hold:
- it is the same check: the same name with the same recorded values in every run on both sides, and
- the proving claim names it exactly (a cover with no wildcard).

A proving result that is itself advisory, or unstable only on the PR, never links. A difference unstable only on the PR is never linked. Advisory differences cap the verdict at could_not_verify, so this rule never produces verified. It runs in live runs and in rejudging.
