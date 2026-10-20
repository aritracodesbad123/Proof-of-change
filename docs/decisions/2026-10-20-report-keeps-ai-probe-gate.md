# A report keeps an AI-probe downgrade

## What changed

When a report is rebuilt, a result that was already lowered because no AI-written probe ran a changed line stays lowered. It is not shown as verified.

## Why

Rebuilding a report re-applies the coverage check. That check restores the verdict from before the coverage check. If a later check had already lowered verified to could not verify, the rebuild put verified back and the report hid the downgrade.

## Decision

If the saved result was already lowered for a missing AI-written probe, apply that same check again after the coverage check. Results that were not lowered are left on the verdict the coverage check already produced. This is display only. It does not re-judge a pull request.

## Alternatives and tradeoffs

- Always apply the AI-probe check on every rebuild. That would lower older verified results that never had an AI-written probe, which changes what the report says about them.
- Stop re-applying the coverage check. Reports of older results would then drift from the coverage rule.

## What it means for you

A result that was already not verified for lack of an AI-written probe stays not verified in the report. Other saved results keep the verdict they had.
