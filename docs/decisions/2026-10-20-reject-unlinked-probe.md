# A probe that checks none of its own claims does not count

## What changed

A probe lists claim patterns and prints observation names. If it has claims, and not one of those patterns matches
any observation it printed, the probe is rejected. The record says why: which claims missed, and that the probe is
not counted.

A rejected probe cannot support verified. It does not count as checking a promise that results stay the same, and
it does not count as the AI-written probe that ran a changed line. A difference it did find is still reported.

The verdict still comes from one function, `verdict_for`. The coverage gate and the AI-probe gate still only lower
a verdict, and both still run before the advisory swarm.

## Why

A probe can name a claim and then print observations under different names. Counting that probe made it look as
if the claim had been checked. It had not.

## Decision

Reject the probe and store the reason on it. Drop its green observations from the verdict. Keep red and amber
observations, so a real difference cannot disappear and the verdict cannot rise. A probe with no claims is not
this case. One matching pattern is enough to keep the probe.

## Alternatives and tradeoffs

- Drop the probe entirely, including differences it found. That could hide a real change and turn needs attention
  into verified. We do not do that.
- Keep counting it and only add a warning. The warning would still let the probe support verified.

## What it means for you

A probe whose patterns match nothing it observed is marked rejected, with a short reason. It cannot be the reason
a result is verified. If it saw a difference, that difference is still in the result.
