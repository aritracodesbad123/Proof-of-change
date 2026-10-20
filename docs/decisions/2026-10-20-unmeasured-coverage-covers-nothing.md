# Unmeasured probe coverage does not cover the change

## What changed

A probe counts as covering a change only when its line coverage was measured and it ran at least one changed
line. A probe with no measured line coverage, including one whose coverage was never recorded, does not count.
Its green observations are dropped from the verdict, and it does not check a promise that results stay the same.
A difference it found is still reported.

The verdict still comes from one function, `verdict_for`. The coverage gate and the AI-probe gate still only lower
a verdict, and both still run before the advisory swarm.

## Why

When coverage could not be measured, the probe used to count as if it had reached the change. A green result then
supported verified even though nobody had shown that the probe ran the changed lines.

## Decision

No measured line coverage means the probe does not cover the change. That can turn verified into could not verify
when a promise in the pull request needed a probe that reached the change. It does not turn needs attention into
anything else, and it does not turn could not verify into verified. A probe that was measured and ran a changed
line still counts, as before.

## Alternatives and tradeoffs

- Keep treating unmeasured probes as before, and only say so in the report. That leaves verified standing on a
  probe that might never have reached the change.
- Fail the whole run when coverage cannot be measured. That stops a check on a machine where the coverage tool
  did not install. Could not verify is enough.

## What it means for you

A verified result no longer rests on a probe whose coverage was not measured. The report says the probe has no
measured line coverage. If that probe saw a difference, the difference is still there.
