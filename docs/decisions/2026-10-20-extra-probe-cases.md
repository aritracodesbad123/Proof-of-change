# Extra cases outside a claim do not count against it

## What changed

When a model-written probe has claims, an observation that belongs to none of those claims does not count against the claim and does not by itself make the verdict needs attention.

## Why

The model sometimes prints extra cases next to the case the claim is about. A difference in an extra case was treated as a change the pull request never mentioned, which failed the claim the probe was written to check.

## Decision

Skip those extra observations when deciding. Say in the reason how many were left out. A differential probe has no claims, so a difference it finds still counts. The claim's own observations are still judged as before.

## Alternatives and tradeoffs

- Let every extra case count. A claim can fail because of a case it did not make.
- Drop the whole probe when it prints an extra case. A real difference in the claimed case would disappear with it.

## What it means for you

Only the observations tied to a claim affect that claim. Extra cases are noted and not counted. Differences from a differential probe are still counted.
