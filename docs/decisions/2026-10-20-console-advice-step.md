# The swarm sits after the verdict on the timeline

**Date:** 2026-10-20
**Status:** accepted

## What changed

The check timeline on the operator console has a new last step, Advice (swarm). The three agents appear there, after the verdict. The step is marked as advice that does not change the verdict. The verdict step now means only the code verdict.

## Why

Putting the three agents inside the verdict step made a demo look as if they helped decide it. They do not. The checker publishes the verdict first. The agents explain it afterwards.

## Decision

Show the agent stages on their own step, after Verdict, with the words "Doesn't change the verdict" on that step. Leave the verdict, the probes, and the cost figures where the checker already records them. The page only changes which label those stages sit under.

## Alternatives and tradeoffs

Leaving the agents inside Verdict would keep the timeline shorter. It would also keep inviting the wrong reading. A separate step costs one more column and makes the order obvious.

## What it means for you

When you watch a check, the green verdict step finishes before Advice (swarm) starts. The agents can be active only on that later step.
