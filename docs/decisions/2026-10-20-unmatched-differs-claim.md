# A claim that expects a difference must have an observation

## What changed

A probe can name a claim and say that claim expects a difference between the two sides. If none of that probe's
observations match the claim's name pattern, the claim was never checked. A result that would have been verified
is now could not verify. The reason names the claim.

The verdict still comes from one function, `verdict_for`. The two older gates, the coverage gate and the
AI-probe gate, still only lower a verdict, and both still run before the advisory swarm.

## Why

A pattern that matches nothing was ignored. The tests could pass, the probe could print other values, and the
result could say verified even though the difference the claim asked about was never looked at.

## Decision

If the verdict is verified and any deciding probe has a claim that expects a difference and matches no observation
name, the verdict becomes could not verify. A result that is already needs attention, or already could not verify,
is left as it is. This can only lower a verdict or leave it unchanged.

## Alternatives and tradeoffs

- Treat the missing observation as needs attention. That would read like a found difference. Nothing was observed,
  so could not verify is the honest result.
- Ignore the claim, as before. That lets verified stand for a check that did not happen.

## What it means for you

A verified result now means a differs claim on a deciding probe actually lined up with an observation. If it did
not, the result says could not verify and names the claim. Other verdicts stay as they were.
