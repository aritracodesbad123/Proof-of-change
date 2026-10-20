# A differs claim that never shows the old behaviour is not a failed claim

## What changed

When a claim says behaviour changes, and the probe's observations for that claim are the same on both sides, the probe is not adequate. The reason says it didn't reproduce the bug. That claim is not failed.

## Why

A claim that behaviour changes is a claim that the old behaviour shows up on the base side. If the probe never builds the input that triggers it, both sides look the same. That used to fail the claim. The probe had not checked the bug.

## Decision

Use this only when the claim expects a difference and at least one observation belongs to it, and none of those observations differ. The probe's changed-line count is cleared, so it cannot support verified. A claim that does show a difference is unchanged. A claim that says behaviour stays the same, and then it changes, is still a failed claim. A differs claim that matches no observation name stays on the existing unmatched-claim rule.

## Alternatives and tradeoffs

- Keep failing the claim. A probe that missed the bug would look like the claim was wrong.
- Ignore the claim and still call the probe adequate. It could support verified without ever showing the old behaviour.

## What it means for you

If a probe does not reproduce the bug on the base side, the result says the probe is not adequate. It does not say the claim failed. A real difference on another claim is still reported.
